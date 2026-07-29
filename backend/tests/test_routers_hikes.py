"""Tests for the /hikes router, via the real FastAPI TestClient.

Mirrors tests/test_routers_profiles.py's token-minting pattern - real JWTs
signed with the same test-only SUPABASE_JWT_SECRET tests/conftest.py sets.
"""

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


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def test_create_hike_requires_authentication(client):
    response = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
    )

    assert response.status_code == 401


def test_get_hikes_only_returns_the_callers_own_hikes(client):
    user_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    user_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    create_a = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
        headers=_auth_headers(user_a),
    )
    assert create_a.status_code == 201

    create_b = client.post(
        "/hikes",
        json={"overall_start_reference": 2189.0, "overall_end_reference": 0.0},
        headers=_auth_headers(user_b),
    )
    assert create_b.status_code == 201

    response = client.get("/hikes", headers=_auth_headers(user_a))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert all(hike["user_id"] == user_a for hike in body)


def test_get_hike_direction_endpoint_returns_nobo_for_a_springer_to_katahdin_hike(client):
    user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    create_response = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
        headers=_auth_headers(user_id),
    )
    assert create_response.status_code == 201
    hike_id = create_response.json()["id"]

    response = client.get(f"/hikes/{hike_id}/direction", headers=_auth_headers(user_id))

    assert response.status_code == 200
    assert response.json() == {"direction": "NOBO"}
