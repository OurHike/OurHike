"""Tests for GET/PUT /preferences/me, via the real FastAPI TestClient.

See ../../../features/IDENTITY_AND_PRIVACY.md for the canonical
UserPreferences model this syncs. `show_closures` is deliberately never part
of it (Map Options: closures are always shown, never hideable) - several
tests below exist specifically to pin that down at the API boundary.
"""

from sqlalchemy import select

from app.models.preferences import UserPreferences
from tests.tokens import auth_headers


def _valid_preferences(**overrides) -> dict:
    body = {
        "trail_name": "Switchback",
        "theme": "dark",
        "unit_system": "imperial",
        "background_source": "usgs_topo_offline",
        "max_background_zoom": 12,
        "show_roads": False,
        "waypoint_types_shown": ["water", "shelter"],
        "layer_detail_level": "standard",
        "auto_rotate_enabled": False,
        "anonymity_window_days": 14,
        "onboarding_completed": True,
        "download_choice_made": True,
        "location_permission_requested": True,
    }
    body.update(overrides)
    return body


def test_get_preferences_me_requires_authentication(client):
    response = client.get("/preferences/me")

    assert response.status_code == 401


def test_put_preferences_creates_a_row_on_first_call(client):
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    put_response = client.put("/preferences/me", json=_valid_preferences(), headers=auth_headers(user_id))
    assert put_response.status_code == 200
    body = put_response.json()
    assert body["trail_name"] == "Switchback"
    assert body["theme"] == "dark"
    assert body["max_background_zoom"] == 12
    assert "updated_at" in body

    get_response = client.get("/preferences/me", headers=auth_headers(user_id))
    assert get_response.status_code == 200
    assert get_response.json()["trail_name"] == "Switchback"


def test_put_preferences_upserts_on_a_second_call(client, db_session):
    user_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    first = client.put("/preferences/me", json=_valid_preferences(theme="light"), headers=auth_headers(user_id))
    assert first.status_code == 200

    second = client.put("/preferences/me", json=_valid_preferences(theme="dark"), headers=auth_headers(user_id))
    assert second.status_code == 200
    assert second.json()["theme"] == "dark"

    get_response = client.get("/preferences/me", headers=auth_headers(user_id))
    assert get_response.status_code == 200
    assert get_response.json()["theme"] == "dark"

    # Upsert, not a duplicate row - exactly one row exists for this profile.
    rows = db_session.execute(select(UserPreferences).where(UserPreferences.profile_id == user_id)).scalars().all()
    assert len(rows) == 1


def test_put_preferences_rejects_an_invalid_theme_value(client):
    user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    response = client.put(
        "/preferences/me",
        json=_valid_preferences(theme="solarized"),
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422


def test_put_preferences_rejects_an_out_of_range_max_background_zoom(client):
    user_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    response = client.put(
        "/preferences/me",
        json=_valid_preferences(max_background_zoom=14),
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422


def test_put_preferences_does_not_accept_a_show_closures_field(client):
    user_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"

    response = client.put(
        "/preferences/me",
        json=_valid_preferences(show_closures=False),
        headers=auth_headers(user_id),
    )

    # extra="forbid" means an unknown field is a real validation error (422),
    # not the field being silently dropped and the request otherwise
    # succeeding (which would be a 200) - assert the real behavior, not just
    # "not silently accepted."
    assert response.status_code == 422
    body = response.json()
    assert any("show_closures" in str(error.get("loc")) for error in body["detail"])


def test_get_repairs_a_stored_background_the_enum_no_longer_carries(client, db_session):
    """`usgs_topo_live` was a valid value when rows were written; the enum
    dropped it. The client's own repair runs on PUT - a GET that arrives
    first used to read the row straight into PreferencesOut and 500, at the
    exact client that could not do anything about it. The read side now
    makes the same move the phone makes: unknown becomes the default."""
    from datetime import UTC, datetime

    from app.models.profile import Profile, Role

    user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    legacy = _valid_preferences(background_source="usgs_topo_live")
    db_session.add(Profile(id=user_id, role=Role.hiker))
    db_session.commit()
    db_session.add(UserPreferences(profile_id=user_id, data=legacy, updated_at=datetime.now(UTC)))
    db_session.commit()

    response = client.get("/preferences/me", headers=auth_headers(user_id))

    assert response.status_code == 200
    assert response.json()["background_source"] == "hiking_topo_live"


def test_get_leaves_a_current_background_alone(client):
    user_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    client.put(
        "/preferences/me",
        json=_valid_preferences(background_source="usgs_topo_offline"),
        headers=auth_headers(user_id),
    )

    response = client.get("/preferences/me", headers=auth_headers(user_id))

    assert response.status_code == 200
    assert response.json()["background_source"] == "usgs_topo_offline"
