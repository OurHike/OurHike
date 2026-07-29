"""Tests for app.core.auth - the JWT-verification/profile-provisioning seam.

Real JWTs are built here with PyJWT, signed with the same
SUPABASE_JWT_SECRET tests/conftest.py sets as a placeholder - this never
talks to a real Supabase project (there isn't one yet), matching
`verify_supabase_jwt`'s job of verifying whatever token Supabase's client
SDK would hand the app.

`get_current_user` and the dependency `require_role(...)` returns are called
directly here (not through the FastAPI TestClient) - their `Depends(...)`
defaults are only meaningful when FastAPI's own DI resolves them for a real
route, so a direct call just passes real values as keyword arguments instead.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from app.config import settings
from app.core.auth import get_current_user, require_role
from app.models.profile import Profile, Role

TEST_SECRET = settings.supabase_jwt_secret


def _make_token(user_id: str, secret: str = TEST_SECRET, expires_delta: timedelta = timedelta(hours=1)) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_accepts_a_validly_signed_token(db_session):
    user_id = "11111111-1111-1111-1111-111111111111"
    token = _make_token(user_id)

    profile = get_current_user(credentials=_credentials(token), db=db_session)

    assert profile.id == user_id


def test_get_current_user_rejects_a_token_signed_with_the_wrong_secret(db_session):
    token = _make_token("22222222-2222-2222-2222-222222222222", secret="a-completely-different-secret")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_an_expired_token(db_session):
    token = _make_token("33333333-3333-3333-3333-333333333333", expires_delta=timedelta(hours=-1))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_user_provisions_a_profile_row_on_first_request_for_a_new_user_id(db_session):
    user_id = "44444444-4444-4444-4444-444444444444"
    token = _make_token(user_id)

    profile = get_current_user(credentials=_credentials(token), db=db_session)

    assert profile.id == user_id
    assert profile.role == Role.hiker

    stored = db_session.execute(select(Profile).where(Profile.id == user_id)).scalar_one()
    assert stored.id == user_id
    assert stored.role == Role.hiker


def test_get_current_user_does_not_duplicate_a_profile_row_on_repeat_requests(db_session):
    user_id = "55555555-5555-5555-5555-555555555555"
    token = _make_token(user_id)

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
