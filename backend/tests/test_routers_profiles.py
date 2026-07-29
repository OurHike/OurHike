"""Tests for GET /profiles/me, via the real FastAPI TestClient."""

from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

TEST_SECRET = settings.supabase_jwt_secret


def _make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def test_get_profiles_me_requires_authentication(client):
    response = client.get("/profiles/me")

    assert response.status_code == 401


def test_get_profiles_me_returns_the_current_users_role_and_display_name(client):
    user_id = "88888888-8888-8888-8888-888888888888"
    token = _make_token(user_id)

    response = client.get("/profiles/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user_id
    assert body["role"] == "hiker"
    assert body["display_name"] is None
    assert "created_at" in body
