import time

import jwt
import pytest
from conftest import OTHER_KEY, bearer, token

from steward_api.models import StewardUser


def test_a_request_with_no_token_is_401_and_says_how_to_authenticate(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_a_token_signed_by_another_key_is_refused(client):
    assert client.get("/me", headers={"Authorization": f"Bearer {token(key=OTHER_KEY)}"}).status_code == 401


def test_an_expired_token_is_refused(client):
    assert client.get("/me", headers={"Authorization": f"Bearer {token(exp=int(time.time()) - 5)}"}).status_code == 401


def test_a_token_without_an_expiry_is_refused_rather_than_trusted_forever(client):
    assert client.get("/me", headers={"Authorization": f"Bearer {token(exp=None)}"}).status_code == 401


def test_a_token_for_another_audience_is_refused(client):
    assert client.get("/me", headers={"Authorization": f"Bearer {token(aud='service_role')}"}).status_code == 401


def test_an_hs256_token_is_refused_when_no_shared_secret_is_configured(client):
    forged = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60},
        "a-guessed-secret-of-thirty-two-bytes!",
        algorithm="HS256",
    )
    assert client.get("/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_an_unsigned_alg_none_token_is_refused(client):
    unsigned = jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60}, None, algorithm="none")
    assert client.get("/me", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_the_first_signed_in_request_creates_the_account_row_with_no_name_and_no_email(client, app):
    response = client.get("/me", headers=bearer("user-1"))
    assert response.status_code == 200
    assert response.json() == {"display_name": None}
    with app.state.sessionmaker() as db:
        row = db.get(StewardUser, "user-1")
        assert row is not None and row.display_name is None
        assert "email" not in StewardUser.__table__.columns


def test_a_display_name_is_trimmed_and_refused_with_control_characters_or_past_40_characters(client):
    assert client.patch("/me", json={"display_name": "  Ridge Runner  "}, headers=bearer("u")).json() == {
        "display_name": "Ridge Runner"
    }
    assert client.patch("/me", json={"display_name": "a\u0000b"}, headers=bearer("u")).status_code == 422
    assert client.patch("/me", json={"display_name": "x" * 41}, headers=bearer("u")).status_code == 422
    assert client.patch("/me", json={"display_name": None}, headers=bearer("u")).json() == {"display_name": None}


def test_deleting_the_account_removes_its_lists_and_name_and_keeps_its_weights_changes_without_a_name(client):
    client.patch("/me", json={"display_name": "Leaver"}, headers=bearer("leaver"))
    client.post("/lists", json={"name": "Mine"}, headers=bearer("leaver"))
    weights = {"club": "Example Trail Club", "deficit": 50, "water": 12, "trail": 6, "cluster": 8, "restricted": 10}
    assert client.post("/weights", json=weights, headers=bearer("leaver")).status_code == 201

    assert client.delete("/me", headers=bearer("leaver")).status_code == 204

    history = client.get("/weights", params={"club": "Example Trail Club"}, headers=bearer("someone")).json()["history"]
    assert len(history) == 1 and history[0]["changed_by"] is None and history[0]["deficit"] == 50


def test_a_deleted_account_cannot_come_back_as_a_fresh_one_with_the_same_sign_in(client, monkeypatch):
    # The review's finding 3: deleting the row let the same token return at
    # once as a stranger, free of its weights cap.
    from steward_api import limits

    monkeypatch.setattr(limits, "WEIGHT_CHANGES_PER_DAY", 1)
    change = {"club": "Example Trail Club", "deficit": 50, "water": 12, "trail": 6, "cluster": 8, "restricted": 10}
    assert client.post("/weights", json=change, headers=bearer("leaver")).status_code == 201
    assert client.delete("/me", headers=bearer("leaver")).status_code == 204
    again = client.post("/weights", json={**change, "deficit": 51}, headers=bearer("leaver"))
    assert again.status_code == 401 and "deleted" in again.json()["detail"]
    assert client.get("/lists", headers=bearer("leaver")).status_code == 401


def test_an_anonymous_supabase_user_is_refused(client):
    anonymous = token("anon-1", is_anonymous=True)
    assert client.get("/me", headers={"Authorization": f"Bearer {anonymous}"}).status_code == 401


@pytest.mark.parametrize("name", ["Admin\u202e", "Trail\u200bBoss", "two\nlines"])
def test_a_display_name_with_invisible_or_control_characters_is_refused(client, name):
    assert client.patch("/me", json={"display_name": name}, headers=bearer("u")).status_code == 422
