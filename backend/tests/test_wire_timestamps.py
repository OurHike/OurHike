"""Every datetime this API serializes carries a UTC designator.

Storage is naive-UTC throughout (the convention documented in
app/models/profile.py), and the gap this file pins shut is at the
serialization boundary: `2026-08-06T12:00:00` with no `Z` is *local* time to
`new Date()`, so an unstamped wire value silently shifts by the reader's UTC
offset - four to five hours along the trail (#254).

The assertions are deliberately about the instant a consumer recovers, not
just about the trailing character. A test that only checked `endswith("Z")`
would still pass if the value underneath were wrong, and "the timestamp is
wrong by exactly one timezone" is the failure this is here to catch.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.profile import Profile, Role
from app.schemas.closure import ClosureOut
from app.schemas.hike import HikeOut
from app.schemas.preferences import PreferencesOut
from app.schemas.profile import ProfileOut
from app.schemas.report import ReportOut
from tests.factories import make_closure
from tests.tokens import auth_headers

_REPORT_PAYLOAD = {
    "type": "blowdown",
    "reporter_type": "thru",
    "lat": 35.6,
    "lon": -83.5,
    "note": "Large tree across the trail near the gap.",
}

_CLOSURE_PAYLOAD = {
    "reason_type": "storm_damage",
    "note": "Large blowdown blocking the trail after the storm.",
    "start_mile_marker": 1408.6,
    "end_mile_marker": 1411.0,
}


def _valid_preferences() -> dict:
    return {
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


def _assert_is_utc_instant(wire: str) -> datetime:
    """The value names its own offset, and parses to the instant it names.

    `fromisoformat` is the stand-in for a consumer that does the ordinary
    thing. What matters is that the result is timezone-aware without the
    caller having to re-attach anything - an aware value cannot be
    misread as local, whatever the reader's own offset is.
    """
    parsed = datetime.fromisoformat(wire)
    assert parsed.tzinfo is not None, f"{wire!r} does not name its own offset"
    assert parsed.utcoffset() == timedelta(0), f"{wire!r} is not UTC"
    return parsed


def test_report_timestamps_are_stamped_utc_end_to_end(client):
    before = datetime.now(timezone.utc)
    response = client.post("/reports", json=_REPORT_PAYLOAD, headers=auth_headers(str(uuid.uuid4())))
    after = datetime.now(timezone.utc)

    assert response.status_code == 201
    body = response.json()

    for field in ("timestamp", "received_at"):
        parsed = _assert_is_utc_instant(body[field])
        # The instant survives the round trip. A value shifted by the
        # reader's offset would fall outside a window this tight.
        assert before - timedelta(seconds=5) <= parsed <= after + timedelta(seconds=5), (
            f"{field} landed outside the request window - the instant shifted"
        )


def test_closure_reported_at_is_stamped_utc_end_to_end(client):
    before = datetime.now(timezone.utc)
    response = client.post("/closures", json=_CLOSURE_PAYLOAD, headers=auth_headers(str(uuid.uuid4())))
    after = datetime.now(timezone.utc)

    assert response.status_code == 201
    body = response.json()

    parsed = _assert_is_utc_instant(body["reported_at"])
    assert before - timedelta(seconds=5) <= parsed <= after + timedelta(seconds=5)
    # Nothing has verified it, so the nullable partner stays null rather
    # than becoming a stamped epoch.
    assert body["verified_at"] is None


def test_closure_verified_at_is_stamped_utc_once_it_is_set(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    maintainer_id = str(uuid.uuid4())
    db_session.add_all([reporter, Profile(id=maintainer_id, role=Role.maintainer)])
    db_session.commit()
    closure = make_closure(db_session, reporter.id, verified_at=datetime(2026, 8, 6, 12, 0, 0))

    response = client.patch(
        f"/closures/{closure.id}",
        json={"status": "closed"},
        headers=auth_headers(maintainer_id),
    )

    assert response.status_code == 200
    assert _assert_is_utc_instant(response.json()["verified_at"]) == datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def test_preferences_updated_at_is_stamped_utc_end_to_end(client):
    user_id = str(uuid.uuid4())
    before = datetime.now(timezone.utc)
    put_response = client.put("/preferences/me", json=_valid_preferences(), headers=auth_headers(user_id))
    after = datetime.now(timezone.utc)

    assert put_response.status_code == 200
    parsed = _assert_is_utc_instant(put_response.json()["updated_at"])
    assert before - timedelta(seconds=5) <= parsed <= after + timedelta(seconds=5)

    # The read path serializes from a stored row rather than one just built
    # in memory, so it is worth asserting separately.
    get_response = client.get("/preferences/me", headers=auth_headers(user_id))
    assert get_response.status_code == 200
    _assert_is_utc_instant(get_response.json()["updated_at"])


def test_profile_created_at_is_stamped_utc_end_to_end(client):
    response = client.get("/profiles/me", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 200
    _assert_is_utc_instant(response.json()["created_at"])


def test_hike_created_at_is_stamped_utc_end_to_end(client):
    response = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 201
    _assert_is_utc_instant(response.json()["created_at"])


def _serialized_created_at(value: datetime) -> str:
    """The wire form of one stored value, through a real response model."""
    profile = ProfileOut(id=str(uuid.uuid4()), role=Role.hiker, display_name=None, created_at=value)
    return profile.model_dump(mode="json")["created_at"]


def test_a_naive_stored_value_is_stamped_rather_than_shifted():
    assert _serialized_created_at(datetime(2026, 8, 6, 12, 0, 0)) == "2026-08-06T12:00:00Z"


def test_an_aware_value_is_converted_to_utc_not_relabelled():
    """The same instant, expressed in UTC - not the wall clock with a Z bolted on.

    Nothing in the app stores aware datetimes today, so this guards the
    serializer's own contract: were one ever to reach it, relabelling
    08:00-04:00 as `08:00Z` would move the event by four hours.
    """
    aware = datetime(2026, 8, 6, 8, 0, 0, tzinfo=timezone(timedelta(hours=-4)))

    assert _serialized_created_at(aware) == "2026-08-06T12:00:00Z"


def test_sub_second_precision_is_not_dropped_by_stamping():
    stored = datetime(2026, 8, 6, 12, 0, 0, 123456)

    assert _serialized_created_at(stored) == "2026-08-06T12:00:00.123456Z"


def test_python_mode_dump_still_yields_real_datetimes():
    """Only the wire format changed.

    The serializer is scoped to JSON so in-process callers keep getting
    `datetime` objects - a string here would break arithmetic in any caller
    that dumps a response model and then compares times.
    """
    stored = datetime(2026, 8, 6, 12, 0, 0)

    dumped = ProfileOut(id=str(uuid.uuid4()), role=Role.hiker, display_name=None, created_at=stored).model_dump()["created_at"]

    assert dumped == stored
    assert isinstance(dumped, datetime)


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (ReportOut, "timestamp"),
        (ClosureOut, "reported_at"),
        (PreferencesOut, "updated_at"),
        (ProfileOut, "created_at"),
        (HikeOut, "created_at"),
    ],
)
def test_openapi_still_documents_these_fields_as_date_time(model, field):
    """Correct values must not cost a vaguer contract.

    `PlainSerializer(return_type=str)` on its own would document these as
    bare strings, so a generated client would stop parsing them as dates -
    trading one silent wrongness for another.
    """
    schema = model.model_json_schema(mode="serialization")["properties"][field]

    assert schema.get("format") == "date-time"
    assert schema.get("type") == "string"


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (ClosureOut, "verified_at"),
        # Nullable since #252: withheld from anyone who is neither the
        # reporter nor a moderator. It moved out of the table above rather
        # than losing its assertion - a withheld field still has to document
        # what it is when it IS sent, or a generated client stops parsing it.
        (ReportOut, "received_at"),
        # Nullable for the ordinary reason rather than a privacy one (#292):
        # a report nobody has confirmed has no confirmation time. Public,
        # unlike its neighbour above - see the field's own comment.
        (ReportOut, "verified_at"),
    ],
)
def test_openapi_documents_a_nullable_timestamp_as_date_time_or_null(model, field):
    schema = model.model_json_schema(mode="serialization")["properties"][field]

    assert {"type": "string", "format": "date-time"} in schema["anyOf"]
    assert {"type": "null"} in schema["anyOf"]
