"""Tests for app.core.auth - the JWT-verification/profile-provisioning seam.

Real JWTs are built here with PyJWT and verified against real keys. Nothing
talks to a live Supabase project: the HS256 tokens are signed with the
placeholder secret tests/conftest.py sets, and the ES256 ones with a keypair
generated in tests/tokens.py, whose public half is handed to the verifier
through the `signing_key_for` seam instead of a network fetch.

Both algorithms are covered because both are real. A hosted project signs
ES256 and publishes a JWKS; a self-hosted one signs HS256 against a shared
secret. See app/core/auth.py for why the token's own header is allowed to
choose between them and why that is not an algorithm-confusion hole.

`get_current_user` and the dependency `require_role(...)` returns are called
directly here (not through the FastAPI TestClient) - their `Depends(...)`
defaults are only meaningful when FastAPI's own DI resolves them for a real
route, so a direct call just passes real values as keyword arguments instead.
"""

from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from app.config import settings
from app.core import auth as auth_module
from app.core.auth import get_current_user, require_role, verify_supabase_jwt
from app.models.profile import Profile, Role
from tests.tokens import es256_keypair, make_es256_token, make_token, other_es256_key


@pytest.fixture
def published_key(monkeypatch):
    """Serve the test keypair's public half where the JWKS would be.

    Patching this seam rather than the whole verifier keeps the signature
    check real - PyJWT still does the ECDSA maths against a genuine key.
    """
    _, public = es256_keypair()
    monkeypatch.setattr(auth_module, "signing_key_for", lambda _token: public)
    return public


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_accepts_a_validly_signed_token(db_session):
    user_id = "11111111-1111-1111-1111-111111111111"
    token = make_token(user_id)

    profile = get_current_user(credentials=_credentials(token), db=db_session)

    assert profile.id == user_id


def test_get_current_user_accepts_the_audience_supabase_actually_issues(db_session):
    """The bug this file could not see, because it never minted the claim.

    Supabase puts `aud: "authenticated"` on every user access token. PyJWT
    refuses a token carrying `aud` when the caller names no audience, so
    verification passed only for tokens Supabase does not issue: the first
    real signed-in request would have returned 401 with a perfectly valid
    token, a correct secret and a good signature.
    """
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    token = make_token(user_id, audience="authenticated")

    profile = get_current_user(credentials=_credentials(token), db=db_session)

    assert profile.id == user_id


def test_get_current_user_rejects_a_token_minted_for_a_different_audience(db_session):
    # Same secret, same signature, wrong consumer - a token issued for some
    # other service is not a token for this one.
    token = make_token("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", audience="some-other-service")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_a_token_carrying_no_audience_at_all(db_session):
    # The shape these tests used to mint. With an audience configured, a
    # token that names none cannot be checked against it, so it is refused
    # rather than waved through.
    token = make_token("cccccccc-cccc-cccc-cccc-cccccccccccc", audience=None)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)

    assert exc_info.value.status_code == 401


def test_verify_supabase_jwt_skips_the_audience_check_when_none_is_configured(monkeypatch, db_session):
    # The escape hatch for a project whose tokens are shaped some other way:
    # an empty setting means "do not check", not "require an empty aud".
    monkeypatch.setattr(settings, "supabase_jwt_audience", "")
    user_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    for token in (make_token(user_id, audience=None), make_token(user_id, audience="anything")):
        profile = get_current_user(credentials=_credentials(token), db=db_session)
        assert profile.id == user_id


def test_get_current_user_rejects_a_token_signed_with_the_wrong_secret(db_session):
    token = make_token("22222222-2222-2222-2222-222222222222", secret="a-completely-different-secret")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_an_expired_token(db_session):
    token = make_token("33333333-3333-3333-3333-333333333333", expires_delta=timedelta(hours=-1))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_user_provisions_a_profile_row_on_first_request_for_a_new_user_id(db_session):
    user_id = "44444444-4444-4444-4444-444444444444"
    token = make_token(user_id)

    profile = get_current_user(credentials=_credentials(token), db=db_session)

    assert profile.id == user_id
    assert profile.role == Role.hiker

    stored = db_session.execute(select(Profile).where(Profile.id == user_id)).scalar_one()
    assert stored.id == user_id
    assert stored.role == Role.hiker


def test_get_current_user_does_not_duplicate_a_profile_row_on_repeat_requests(db_session):
    user_id = "55555555-5555-5555-5555-555555555555"
    token = make_token(user_id)

    get_current_user(credentials=_credentials(token), db=db_session)
    get_current_user(credentials=_credentials(token), db=db_session)

    rows = db_session.execute(select(Profile).where(Profile.id == user_id)).scalars().all()
    assert len(rows) == 1


def test_require_role_rejects_a_non_matching_role_with_403(db_session):
    profile = Profile(id="66666666-6666-6666-6666-666666666666", role=Role.hiker)
    db_session.add(profile)
    db_session.commit()

    dependency = require_role("maintainer", "club_admin")

    with pytest.raises(HTTPException) as exc_info:
        dependency(profile=profile)

    assert exc_info.value.status_code == 403


def test_require_role_allows_a_matching_role_through(db_session):
    profile = Profile(id="77777777-7777-7777-7777-777777777777", role=Role.maintainer)
    db_session.add(profile)
    db_session.commit()

    dependency = require_role("maintainer", "club_admin")

    result = dependency(profile=profile)

    assert result is profile


# The algorithm a hosted project really signs with. Until this existed the
# suite verified only HS256, every test passed, and the first real signed-in
# request would still have come back 401 - the same shape of gap that the
# missing `aud` claim left, and the reason tokens.py mints realistic tokens
# rather than convenient ones.


def test_verify_accepts_the_es256_token_a_hosted_project_issues(published_key, db_session):
    profile = get_current_user(credentials=_credentials(make_es256_token("hiker-es256")), db=db_session)

    assert profile.id == "hiker-es256"


def test_verify_reads_the_claims_off_an_es256_token(published_key):
    claims = verify_supabase_jwt(make_es256_token("hiker-es256"))

    assert claims["sub"] == "hiker-es256"
    assert claims["aud"] == settings.supabase_jwt_audience


def test_verify_rejects_an_es256_token_signed_by_some_other_key(published_key):
    # The whole point of asymmetric verification: a well-formed token with a
    # plausible `kid` is still worthless without the project's private key.
    forged = make_es256_token("intruder", private_key=other_es256_key())

    with pytest.raises(jwt.InvalidSignatureError):
        verify_supabase_jwt(forged)


def test_es256_verification_needs_no_shared_secret(published_key, monkeypatch):
    # A hosted project has no JWT secret to configure, so verification has to
    # work with the setting empty - which is exactly how it will be deployed.
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")

    assert verify_supabase_jwt(make_es256_token("hiker-es256"))["sub"] == "hiker-es256"


def test_an_expired_es256_token_is_rejected_like_any_other(published_key):
    stale = make_es256_token("hiker-es256", expires_delta=timedelta(hours=-1))

    with pytest.raises(jwt.ExpiredSignatureError):
        verify_supabase_jwt(stale)


def test_hs256_still_works_because_self_hosted_supabase_signs_that_way(db_session):
    # Not a legacy path being tolerated. OurHikeValues.md leans on self-hosting
    # as the thing that keeps this project inheritable, and self-hosted
    # Supabase signs HS256 against JWT_SECRET.
    profile = get_current_user(credentials=_credentials(make_token("hiker-hs256")), db=db_session)

    assert profile.id == "hiker-hs256"


def test_hs256_is_refused_when_no_secret_is_configured(monkeypatch):
    # Rather than verifying against an empty string, which PyJWT will happily
    # do - an empty HMAC key is a valid HMAC key, so this would accept tokens
    # anyone could mint.
    token = make_token("hiker-hs256")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")

    with pytest.raises(jwt.InvalidKeyError):
        verify_supabase_jwt(token)


def test_an_unsupported_algorithm_is_refused_rather_than_defaulted(published_key):
    # `none` is the canonical unsigned-token attack. Refusing every algorithm
    # not on the list means it never reaches a key at all.
    unsigned = jwt.encode({"sub": "intruder"}, key="", algorithm="none")

    with pytest.raises(jwt.InvalidAlgorithmError):
        verify_supabase_jwt(unsigned)


def test_an_es256_token_cannot_be_verified_with_the_hmac_secret(monkeypatch):
    # The algorithm-confusion shape, asserted rather than argued. A token
    # claiming ES256 must reach the JWKS key; it must never fall through to
    # the shared secret, whatever that secret happens to be.
    def refuse(_token):
        raise AssertionError("asymmetric verification must not consult the JWKS stub")

    monkeypatch.setattr(auth_module, "signing_key_for", refuse)

    with pytest.raises(AssertionError):
        verify_supabase_jwt(make_es256_token("hiker-es256"))


def test_a_malformed_token_fails_as_an_auth_error_not_a_crash(db_session):
    # get_unverified_header runs before any key lookup, so garbage has to come
    # back 401 rather than 500.
    with pytest.raises(HTTPException) as raised:
        get_current_user(credentials=_credentials("not-a-jwt"), db=db_session)

    assert raised.value.status_code == 401
