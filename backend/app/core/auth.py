"""The auth seam: verifying a Supabase-issued JWT and resolving/provisioning
the local Profile row it maps to.

Supabase Auth (../../../features/AUTHENTICATION.md) issues and verifies its
own JWTs on sign-in (Google/Apple/email, MFA, email verification all happen
there) - this backend never issues a token itself, only verifies the one
Supabase's client SDK hands back on each request.

`verify_supabase_jwt` was kept as one small, isolated function on purpose,
because *how* to verify was not knowable without a real project to look at.
It is now, and the answer turned out to be both.

**A hosted Supabase project signs with ES256 and publishes the public half
as a JWKS.** Confirmed against a token this project really issued: the
header reads `{"alg": "ES256", "kid": "..."}`. There is no shared secret in
that arrangement, so `SUPABASE_JWT_SECRET` is not merely unused, it does not
exist to be set.

**A self-hosted Supabase signs with HS256 against `JWT_SECRET`.** That path
is not legacy cruft to be tidied away: OurHikeValues.md leans on
self-hosting as the escape hatch that keeps this project inheritable
(values #6 and #7), and dropping HS256 would quietly close it.

So the algorithm named in the token's own header selects the key, and each
branch pins exactly one algorithm and one source of key material. That
dispatch is the part worth reviewing carefully, because reading `alg` off an
unverified header is how algorithm-confusion attacks start. The attack is
substituting a key the verifier will accept for one it should not - classically,
handing an RS256 *public* key back as the HMAC secret. It cannot happen here:
the HS256 branch only ever uses `settings.supabase_jwt_secret`, a value that
never appears in the JWKS and is never derived from the token, and the
asymmetric branch only ever uses a key fetched from the project's own JWKS
endpoint. Neither branch can be steered to the other's key material, and an
`alg` naming anything else is refused outright rather than defaulted.
"""

from collections.abc import Iterable
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.orm import commit_and_refresh
from app.db.session import get_db
from app.models.profile import Profile, Role

# The asymmetric algorithms a Supabase project can sign with. ES256 is what
# hosted projects issue today; RS256 is accepted because Supabase's own key
# settings offer it and a project switched to it should not need a code change
# to keep working.
ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")

# auto_error=False so a missing/malformed Authorization header doesn't short
# -circuit into FastAPI's own default response - `HTTPBearer`'s built-in
# auto_error path returns 403, not 401, on a missing header, which would be
# the wrong status for "not authenticated". get_current_user below raises
# 401 itself instead, in every no-credentials case.
bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _jwk_client() -> jwt.PyJWKClient:
    """The project's published signing keys.

    Built once and cached, because PyJWKClient does its own key caching and a
    fresh client per request would fetch the key set on every single API call.
    """
    return jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


def signing_key_for(token: str) -> object:
    """The public key this token says it was signed with.

    A seam of its own so tests can supply a key without reaching the network -
    verifying a real signature against a real key is the point of those tests,
    and fetching someone's JWKS to do it is not.
    """
    return _jwk_client().get_signing_key_from_jwt(token).key


def verify_supabase_jwt(token: str) -> dict:
    """Decode and verify a Supabase-issued JWT, returning its claims.

    Raises `jwt.PyJWTError` (or a subclass, e.g. `InvalidSignatureError` /
    `ExpiredSignatureError`) on a bad signature or an expired token -
    callers are expected to translate that into an HTTP 401, not to treat a
    verification failure as a 500. `InvalidAlgorithmError` for an `alg` this
    does not accept is deliberately in that same family, so an unexpected
    signing algorithm reaches a hiker as "not signed in" rather than as a 500.

    The `audience` argument is load-bearing and not optional politeness.
    PyJWT refuses a token that carries an `aud` claim when the caller named
    no audience - `_validate_aud` raises `InvalidAudienceError` on exactly
    that combination - and every Supabase user access token carries
    `aud: "authenticated"`. Without this, verification succeeded only for
    tokens Supabase does not issue: the first real signed-in request would
    have come back 401, with the token, the secret and the signature all
    perfectly correct.
    """
    algorithm = jwt.get_unverified_header(token).get("alg")

    if algorithm in ASYMMETRIC_ALGORITHMS:
        key: object = signing_key_for(token)
    elif algorithm == "HS256":
        if not settings.supabase_jwt_secret:
            # A hosted project has no shared secret to configure, so this is
            # not a misconfiguration to shout about on every request - it is
            # an HS256 token arriving at a deployment that verifies asymmetric
            # ones. Refusing it is the correct answer, and saying which of the
            # two is missing is what makes the 401 diagnosable.
            raise jwt.InvalidKeyError("Token is signed with HS256 but SUPABASE_JWT_SECRET is not set.")
        key = settings.supabase_jwt_secret
    else:
        raise jwt.InvalidAlgorithmError(f"Unsupported signing algorithm: {algorithm!r}")

    audience = settings.supabase_jwt_audience
    return jwt.decode(
        token,
        key,
        # The single algorithm the header named, not the whole allowed set.
        # It has already been checked against that set above, and narrowing to
        # one leaves no room for a token to be verified under an algorithm
        # other than the one it claims.
        algorithms=[algorithm],
        # An empty setting means "this project's tokens are shaped some other
        # way" - skip the check rather than demand a claim that is not there.
        **({"audience": audience} if audience else {"options": {"verify_aud": False}}),
    )


def _get_or_create_profile(db: Session, user_id: str) -> Profile:
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(id=user_id, role=Role.hiker)
        db.add(profile)
        try:
            commit_and_refresh(db, profile)
        except IntegrityError:
            # Check-then-insert, so a user's parallel first requests race
            # here - the seam every authenticated request crosses - and the
            # loser used to 500 (#658, the #265 shape). The other request's
            # row is exactly the row this one wanted.
            db.rollback()
            profile = db.get(Profile, user_id)
            if profile is None:
                raise
    return profile


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile:
    """Resolve the current Profile from a bearer JWT, provisioning one if needed.

    On first successful verification of a Supabase user id with no matching
    local `profiles` row, a new one is auto-provisioned (role defaults to
    `hiker`) - this is the "at least enough to identify a reporter and a
    moderator" local identity TECHNICAL_ARCHITECTURE.md's Backend section
    calls for, without duplicating Supabase's own user data.

    A row carrying `deleted_at` is refused rather than returned; see the
    comment at the check, which is the load-bearing half of #895.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        claims = verify_supabase_jwt(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject claim")

    profile = _get_or_create_profile(db, user_id)

    # A deleted account cannot be signed back into (#895). This is not
    # belt-and-braces: this backend has no way to delete the Supabase Auth
    # user - that needs a service-role key app/config.py does not hold - so
    # after a deletion the hiker's Supabase session is still valid and its
    # token still verifies above. Without this line the very next request
    # would sail through `_get_or_create_profile`, find the scrubbed row, and
    # hand the account straight back, minus the trail name.
    #
    # 401 rather than 403, and the wording matters: this is "you are not
    # signed in to anything", which is true, rather than "you may not do
    # this", which would imply the account is still there. The client's
    # `NotSignedInError` path already treats 401 as sign-out (lib/api.ts).
    if profile.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This account has been deleted")

    return profile


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile | None:
    """Like `get_current_user`, but returns None instead of raising.

    For endpoints that work with or without an account but still want to
    know who is asking, if anyone. Two kinds of caller need it, and they are
    not the same kind:

      - A READ that has never needed an account (browsing), which still
        wants the token when there is one so a reporter can see their own
        unmoderated report - app/routers/reports.py.
      - A WRITE this project decided not to gate, which is
        app/routers/app_failures.py and nothing else. Requiring an account
        before somebody can say the app nearly got them lost gets the
        priority backwards; knowing WHICH account, when there is one, is
        still worth having.

    Lived privately in routers/reports.py until the second caller arrived.
    A bad or expired token is treated as no token rather than as an error,
    which is the behaviour both callers want: the request is one that works
    anonymously, so an unusable credential should not turn it into a 401.
    """
    if credentials is None:
        return None
    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


def require_role(*roles: str):
    """Return a FastAPI dependency that only lets the given roles through.

    `roles` are plain strings (e.g. "maintainer", "club_admin") - `Role` is a
    `str` subclass, so `profile.role` compares equal to the matching string
    directly, no need to coerce either side.
    """

    def dependency(profile: Profile = Depends(get_current_user)) -> Profile:
        allowed: Iterable[str] = roles
        if profile.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return profile

    return dependency
