"""Tests for GET/PUT /preferences/me, via the real FastAPI TestClient.

See ../../../features/IDENTITY_AND_PRIVACY.md for the canonical
UserPreferences model this syncs. `show_closures` is deliberately never part
of it (Map Options: closures are always shown, never hideable) - several
tests below exist specifically to pin that down at the API boundary.
"""

import uuid

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
        "hiking_detail_level": "fine",
        "map_style": "field",
        "red_light_enabled": False,
        "show_roads": False,
        "drought_layer_shown": False,
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


def test_put_preferences_rejects_an_unknown_hiking_detail_level(client):
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    response = client.put(
        "/preferences/me",
        json=_valid_preferences(hiking_detail_level="ultra"),
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422


def test_get_defaults_hiking_detail_for_a_blob_written_before_it_existed(client, db_session):
    """Rows synced before #276 have no hiking_detail_level key at all, and a
    stored blob is not a client that can be asked to re-sync first. The read
    side answers with Standard - the documented recommendation, and the level
    a hiker who never made the choice should get."""
    from datetime import UTC, datetime

    from app.models.profile import Profile, Role

    user_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    legacy = _valid_preferences()
    del legacy["hiking_detail_level"]
    db_session.add(Profile(id=user_id, role=Role.hiker))
    db_session.commit()
    db_session.add(UserPreferences(profile_id=user_id, data=legacy, updated_at=datetime.now(UTC)))
    db_session.commit()

    response = client.get("/preferences/me", headers=auth_headers(user_id))

    assert response.status_code == 200
    assert response.json()["hiking_detail_level"] == "standard"


def test_put_preferences_round_trips_the_hiking_detail_level(client):
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    put_response = client.put("/preferences/me", json=_valid_preferences(), headers=auth_headers(user_id))
    assert put_response.status_code == 200
    assert put_response.json()["hiking_detail_level"] == "fine"

    get_response = client.get("/preferences/me", headers=auth_headers(user_id))
    assert get_response.json()["hiking_detail_level"] == "fine"


def test_put_preferences_rejects_an_unknown_map_style(client):
    """All five specced styles are shipped and accepted; a style outside the
    set - a typo, or a future style syncing from a newer client - must 422
    rather than store as a preference that comes back unrenderable."""
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    response = client.put(
        "/preferences/me",
        json=_valid_preferences(map_style="sepia"),
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422


def test_put_preferences_round_trips_every_shipped_map_style(client):
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    for style in ["quiet_pine", "field", "night_hike", "parchment", "ridgeline"]:
        response = client.put(
            "/preferences/me",
            json=_valid_preferences(map_style=style),
            headers=auth_headers(user_id),
        )
        assert response.status_code == 200
        assert response.json()["map_style"] == style


def test_get_defaults_map_style_for_a_blob_written_before_it_existed(client, db_session):
    """Rows synced before the map-style keys have neither, and the read side
    answers Field with red light off - the reviewed default, and never the
    red sheet."""
    from datetime import UTC, datetime

    from app.models.profile import Profile, Role

    user_id = "99999999-9999-9999-9999-999999999999"
    legacy = _valid_preferences()
    del legacy["map_style"]
    del legacy["red_light_enabled"]
    db_session.add(Profile(id=user_id, role=Role.hiker))
    db_session.commit()
    db_session.add(UserPreferences(profile_id=user_id, data=legacy, updated_at=datetime.now(UTC)))
    db_session.commit()

    response = client.get("/preferences/me", headers=auth_headers(user_id))

    assert response.status_code == 200
    assert response.json()["map_style"] == "field"
    assert response.json()["red_light_enabled"] is False


def test_put_preferences_round_trips_night_hike_with_red_light(client):
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    put_response = client.put(
        "/preferences/me",
        json=_valid_preferences(map_style="night_hike", red_light_enabled=True),
        headers=auth_headers(user_id),
    )
    assert put_response.status_code == 200
    assert put_response.json()["map_style"] == "night_hike"
    assert put_response.json()["red_light_enabled"] is True

    get_response = client.get("/preferences/me", headers=auth_headers(user_id))
    assert get_response.json()["map_style"] == "night_hike"
    assert get_response.json()["red_light_enabled"] is True


def test_get_before_any_put_is_a_404_naming_the_state(client):
    """The documented pre-first-PUT state (#322): a hiker who has never
    synced has no row, and the 404's detail says so - "no preferences yet"
    and "wrong endpoint" must not be the same blank answer."""
    response = client.get("/preferences/me", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 404
    assert "No synced preferences yet" in response.json()["detail"]
