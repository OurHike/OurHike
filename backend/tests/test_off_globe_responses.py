"""A response never serves a coordinate pair that is not a point on Earth (#1861).

#1861 - The backend still stores, moderates and serves off-globe coordinates:
five request schemas, the moderation queue, and GET /reports, /closures and
/field-notes. Item 1 there (bounding the request schemas) waits for a
contract boundary, so a row at (1000, -5000) can still be stored. These tests
store one through the route a client would actually use where one exists,
then read it back through every response that issue names: the moderation
queue (item 2) and the three public lists (item 3).

The rule is app/schemas/common.py's `on_globe_or_none`, the same rule as
pipeline/export_conditions.py's `_null_off_globe()` for the baked files.
"""

import math

import pytest

from app.models.closure import ModerationStatus
from app.models.profile import Role
from app.models.report import Report, ReportType, Visibility
from app.schemas.common import on_globe_or_none
from tests.factories import make_closure, make_profile
from tests.tokens import auth_headers

OFF_GLOBE = (1000.0, -5000.0)
ON_GLOBE = (35.6, -83.5)


# --- The rule ----------------------------------------------------------------


@pytest.mark.parametrize(
    "pair",
    [ON_GLOBE, (90.0, 180.0), (-90.0, -180.0), (0.0, 0.0), (None, None)],
)
def test_a_point_on_earth_or_no_point_is_served_unchanged(pair):
    assert on_globe_or_none(*pair) == pair


@pytest.mark.parametrize(
    "pair",
    [
        OFF_GLOBE,
        (90.0001, 0.0),
        (0.0, -180.0001),
        # One half of a pair places nothing.
        (35.6, None),
        (None, -83.5),
        # A good latitude does not rescue a bad longitude.
        (35.6, 200.0),
    ],
)
def test_a_pair_off_the_globe_or_half_missing_is_nulled_whole(pair):
    assert on_globe_or_none(*pair) == (None, None)


def test_a_nan_or_infinite_half_is_left_alone_for_the_loud_refusal():
    """The pipeline's rule, kept: a non-finite half is a fault to surface,
    not a bound to quietly enforce. FiniteFloat refuses one at the request."""
    lat, lon = on_globe_or_none(math.nan, 10.0)
    assert math.isnan(lat) and lon == 10.0
    assert on_globe_or_none(math.inf, None) == (math.inf, None)


# --- Reports -----------------------------------------------------------------


def _report_at(db_session, lat, lon):
    report = Report(
        reporter_id=make_profile(db_session).id,
        type=ReportType.blowdown,
        reporter_type="day",
        visibility=Visibility.public,
        lat=lat,
        lon=lon,
        mile=207.3,
        note="tree down across the trail",
    )
    db_session.add(report)
    db_session.commit()
    return report


def test_the_moderation_queue_shows_an_off_globe_report_with_no_location_and_keeps_the_rest(client, db_session):
    report = _report_at(db_session, *OFF_GLOBE)
    moderator = make_profile(db_session, Role.maintainer).id

    queue = client.get("/moderation/queue", headers=auth_headers(moderator))

    assert queue.status_code == 200
    row = next(r for r in queue.json()["reports"] if r["id"] == report.id)
    assert (row["lat"], row["lon"]) == (None, None)
    assert row["mile"] == 207.3
    assert row["note"] == "tree down across the trail"


def test_get_reports_serves_an_off_globe_report_with_no_location(client, db_session):
    off = _report_at(db_session, *OFF_GLOBE)
    on = _report_at(db_session, *ON_GLOBE)
    moderator = make_profile(db_session, Role.maintainer).id
    for report in (off, on):
        assert client.post(f"/reports/{report.id}/verify", json={}, headers=auth_headers(moderator)).status_code == 200

    listed = {r["id"]: r for r in client.get("/reports").json()}

    assert (listed[off.id]["lat"], listed[off.id]["lon"]) == (None, None)
    assert listed[off.id]["mile"] == 207.3
    assert (listed[on.id]["lat"], listed[on.id]["lon"]) == ON_GLOBE


def test_the_stored_row_is_not_changed(client, db_session):
    """This is the wire, not the record: the moderator's eventual fix, or
    item 1's refusal, still has the stored value to look at."""
    report = _report_at(db_session, *OFF_GLOBE)
    moderator = make_profile(db_session, Role.maintainer).id
    client.get("/moderation/queue", headers=auth_headers(moderator))

    db_session.refresh(report)
    assert (report.lat, report.lon) == OFF_GLOBE


# --- Closures ----------------------------------------------------------------


def test_get_closures_nulls_only_the_end_that_is_off_the_globe(client, db_session):
    closure = make_closure(
        db_session,
        make_profile(db_session).id,
        start_lat=OFF_GLOBE[0],
        start_lon=OFF_GLOBE[1],
        end_lat=ON_GLOBE[0],
        end_lon=ON_GLOBE[1],
        moderation_status=ModerationStatus.verified,
    )

    row = next(r for r in client.get("/closures").json() if r["id"] == closure.id)

    assert (row["start_lat"], row["start_lon"]) == (None, None)
    assert (row["end_lat"], row["end_lon"]) == ON_GLOBE
    assert (row["start_mile_marker"], row["end_mile_marker"]) == (1.0, 2.0)


def test_the_moderation_queue_shows_an_off_globe_closure_end_with_no_location(client, db_session):
    closure = make_closure(
        db_session,
        make_profile(db_session).id,
        start_lat=ON_GLOBE[0],
        start_lon=ON_GLOBE[1],
        end_lat=OFF_GLOBE[0],
        end_lon=OFF_GLOBE[1],
    )
    moderator = make_profile(db_session, Role.maintainer).id

    queue = client.get("/moderation/queue", headers=auth_headers(moderator)).json()

    row = next(r for r in queue["closures"] if r["id"] == closure.id)
    assert (row["start_lat"], row["start_lon"]) == ON_GLOBE
    assert (row["end_lat"], row["end_lon"]) == (None, None)


# --- Field notes -------------------------------------------------------------


def test_a_field_note_posted_off_the_globe_is_served_with_no_location(client, db_session):
    """Through the real route: FieldNoteCreate still accepts the pair
    (item 1 of #1861), so this is what a client can actually store today."""
    author = make_profile(db_session).id
    posted = client.post(
        "/field-notes",
        json={
            "poi_id": "atc_shelters:abc-123",
            "lat": OFF_GLOBE[0],
            "lon": OFF_GLOBE[1],
            "mile": 207.3,
            "observation": "dry",
            "reporter_type": "section",
        },
        headers=auth_headers(author),
    )
    assert posted.status_code == 201, posted.text
    assert (posted.json()["lat"], posted.json()["lon"]) == (None, None)

    for listed in (client.get("/field-notes").json(), client.get("/field-notes?poi_id=atc_shelters:abc-123").json()):
        row = next(r for r in listed if r["id"] == posted.json()["id"])
        assert (row["lat"], row["lon"]) == (None, None)
        assert row["mile"] == 207.3
