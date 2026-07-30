"""Tests for the `/reports` router - community condition reports.

See ../../features/REPORT_A_PROBLEM.md for the feature this mirrors. The
two server-controlled fields (`visibility`, `severity`) and the
server-authored `timestamp` are the load-bearing behaviors here - none of
them can be set or overridden by whatever a client sends in the request
body, only derived/assigned server-side.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.models.profile import Profile, Role
from app.models.report import Report, ReporterType, ReportStatus, ReportType, Visibility

TEST_SECRET = settings.supabase_jwt_secret


def _make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


_VALID_PAYLOAD = {
    "type": "blowdown",
    "reporter_type": "thru",
    "lat": 35.6,
    "lon": -83.5,
    "note": "Large tree across the trail near the gap.",
}


def test_create_report_requires_authentication(client):
    response = client.post("/reports", json=_VALID_PAYLOAD)

    assert response.status_code == 401


def test_create_report_persists_the_authoring_timestamp_not_the_request_time(client):
    user_id = str(uuid.uuid4())
    # A client-supplied timestamp is not a field ReportCreate declares, so
    # it should be silently dropped, not applied - assert the server's own
    # clock won regardless.
    payload = dict(_VALID_PAYLOAD, timestamp="1999-01-01T00:00:00Z")

    before = datetime.now(timezone.utc)
    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))
    after = datetime.now(timezone.utc)

    assert response.status_code == 201
    body = response.json()
    stored_timestamp = datetime.fromisoformat(body["timestamp"]).replace(tzinfo=timezone.utc)

    assert stored_timestamp.year != 1999
    assert before - timedelta(seconds=5) <= stored_timestamp <= after + timedelta(seconds=5)


def test_create_report_defaults_bad_hikers_type_to_internal_only_visibility(client):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, type="bad_hikers")

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["visibility"] == "internal_only"


@pytest.mark.parametrize("report_type", ["blowdown", "trash", "flooding", "shelter_repair", "animals"])
def test_create_report_defaults_the_other_five_types_to_public_visibility(client, report_type):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, type=report_type)

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["visibility"] == "public"


def test_create_report_ignores_a_client_supplied_severity_field(client):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, severity="serious")

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["severity"] == "normal"


def test_public_list_reports_excludes_internal_only_reports(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    public_report = Report(
        reporter_id=reporter.id,
        type=ReportType.trash,
        reporter_type=ReporterType.day,
        visibility=Visibility.public,
    )
    internal_report = Report(
        reporter_id=reporter.id,
        type=ReportType.bad_hikers,
        reporter_type=ReporterType.day,
        visibility=Visibility.internal_only,
    )
    db_session.add_all([public_report, internal_report])
    db_session.commit()

    response = client.get("/reports")

    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert public_report.id in ids
    assert internal_report.id not in ids


def test_public_list_reports_excludes_dismissed_reports(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    active_report = Report(
        reporter_id=reporter.id,
        type=ReportType.flooding,
        reporter_type=ReporterType.section,
        visibility=Visibility.public,
        status=ReportStatus.submitted,
    )
    dismissed_report = Report(
        reporter_id=reporter.id,
        type=ReportType.flooding,
        reporter_type=ReporterType.section,
        visibility=Visibility.public,
        status=ReportStatus.dismissed,
    )
    db_session.add_all([active_report, dismissed_report])
    db_session.commit()

    response = client.get("/reports")

    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert active_report.id in ids
    assert dismissed_report.id not in ids


def test_reporter_can_view_their_own_internal_only_report(client, db_session):
    user_id = str(uuid.uuid4())
    reporter = Profile(id=user_id, role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    internal_report = Report(
        reporter_id=reporter.id,
        type=ReportType.bad_hikers,
        reporter_type=ReporterType.thru,
        visibility=Visibility.internal_only,
    )
    db_session.add(internal_report)
    db_session.commit()

    anonymous_response = client.get(f"/reports/{internal_report.id}")
    owner_response = client.get(f"/reports/{internal_report.id}", headers=_auth_headers(user_id))

    assert anonymous_response.status_code == 404
    assert owner_response.status_code == 200
    assert owner_response.json()["id"] == internal_report.id


def test_list_reports_requires_no_authentication(client):
    response = client.get("/reports")

    assert response.status_code == 200


# --- Offline-authored reports -------------------------------------------
#
# WIREFRAMES.md is explicit that a report carries "the moment of writing,
# not of sending", that the outbox holds queued reports "with their
# authored timestamps", and that `9c`'s offline outbox syncs them "with
# their original timestamps". A server-assigned creation time cannot
# express any of that: a blowdown written on Monday and synced on
# Thursday would be recorded as Thursday, which changes how a maintainer
# prioritises it and, for a `bad_hikers` report, distorts the timeline of
# a safety investigation.
#
# So there is one sanctioned, bounded channel for it - `authored_at` -
# separate from the raw `timestamp` key, which stays ignored (see the
# test above). A client's claim about when it wrote something is a claim,
# not a fact, so `received_at` records server truth alongside it and a
# future-dated claim is refused outright.


def test_create_report_accepts_a_client_authored_at_for_a_report_written_offline(client):
    user_id = str(uuid.uuid4())
    authored = datetime.now(timezone.utc) - timedelta(days=3)
    payload = dict(_VALID_PAYLOAD, authored_at=authored.isoformat())

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["timestamp"]).replace(tzinfo=timezone.utc)
    assert abs((stored - authored).total_seconds()) < 5


def test_create_report_defaults_the_timestamp_to_now_when_authored_at_is_omitted(client):
    user_id = str(uuid.uuid4())
    before = datetime.now(timezone.utc)

    response = client.post("/reports", json=_VALID_PAYLOAD, headers=_auth_headers(user_id))

    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["timestamp"]).replace(tzinfo=timezone.utc)
    assert stored >= before - timedelta(seconds=5)


def test_create_report_records_received_at_as_server_time_not_the_clients_claim(client):
    user_id = str(uuid.uuid4())
    authored = datetime.now(timezone.utc) - timedelta(days=3)
    payload = dict(_VALID_PAYLOAD, authored_at=authored.isoformat())
    before = datetime.now(timezone.utc)

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    received = datetime.fromisoformat(response.json()["received_at"]).replace(tzinfo=timezone.utc)
    # Server truth, so a backdated claim can always be told apart from a
    # report that really was filed three days ago.
    assert received >= before - timedelta(seconds=5)
    assert received - authored > timedelta(days=2)


def test_create_report_rejects_an_authored_at_in_the_future(client):
    user_id = str(uuid.uuid4())
    payload = dict(
        _VALID_PAYLOAD,
        authored_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 422


def test_create_report_tolerates_small_clock_skew_on_authored_at(client):
    # Phone clocks drift; a minute ahead is skew, not tampering.
    user_id = str(uuid.uuid4())
    payload = dict(
        _VALID_PAYLOAD,
        authored_at=(datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
    )

    response = client.post("/reports", json=payload, headers=_auth_headers(user_id))

    assert response.status_code == 201


def test_an_outbox_flush_keeps_each_reports_own_authored_at(client):
    """TESTING.md item 13's server-side half: three reports written offline
    at different times, all synced in one burst, keep their own times."""
    user_id = str(uuid.uuid4())
    headers = _auth_headers(user_id)
    authored = [datetime.now(timezone.utc) - timedelta(days=d) for d in (5, 3, 1)]

    for when in authored:
        response = client.post(
            "/reports",
            json=dict(_VALID_PAYLOAD, authored_at=when.isoformat()),
            headers=headers,
        )
        assert response.status_code == 201

    listed = client.get("/reports").json()
    stored = sorted(datetime.fromisoformat(r["timestamp"]).replace(tzinfo=timezone.utc) for r in listed)

    assert len(stored) == 3
    for actual, expected in zip(stored, sorted(authored)):
        assert abs((actual - expected).total_seconds()) < 5


# --- Invasive species ----------------------------------------------------
#
# An eighth type (features/REPORT_A_PROBLEM.md, added 2026-07-30) for problem
# plants or animals disrupting the local environment. Structurally an ordinary
# condition report - description, photos, location - so the tests here are
# about it being wired in as one, and specifically about it NOT inheriting the
# two behaviours that would be wrong for it.


_INVASIVE = {
    "type": "invasive_species",
    "reporter_type": "thru",
    "lat": 37.9,
    "lon": -79.1,
    "note": "Large stand of Japanese knotweed spreading along the creek crossing.",
}


def test_create_invasive_species_report(client):
    response = client.post("/reports", json=_INVASIVE, headers=_auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    assert response.json()["type"] == "invasive_species"


def test_invasive_species_is_public_like_every_other_condition_type(client):
    """Nothing in an invasive report identifies a person, so none of the
    bad_hikers reasoning for internal_only applies."""
    body = client.post("/reports", json=_INVASIVE, headers=_auth_headers(str(uuid.uuid4()))).json()

    assert body["visibility"] == Visibility.public.value


def test_invasive_species_appears_in_the_public_report_list(client):
    client.post("/reports", json=_INVASIVE, headers=_auth_headers(str(uuid.uuid4())))

    listed = [r for r in client.get("/reports").json() if r["type"] == "invasive_species"]

    assert len(listed) == 1


def test_invasive_species_can_be_verified_unlike_a_thanks(client, db_session):
    """There IS something to verify about a species sighting, so it uses the
    normal moderation queue - the exception carved out for `thanks` must not
    have widened to cover every new type."""
    moderator = Profile(id=str(uuid.uuid4()), role=Role.club_admin, display_name="Mod")
    db_session.add(moderator)
    db_session.commit()

    created = client.post("/reports", json=_INVASIVE, headers=_auth_headers(str(uuid.uuid4()))).json()
    response = client.post(
        f"/reports/{created['id']}/verify",
        json={"severity": "normal"},
        headers=_auth_headers(moderator.id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == ReportStatus.verified.value


def test_invasive_species_still_carries_a_photo_and_an_authored_time(client):
    """The user-facing ask was description + photos + location + when."""
    authored = datetime.now(timezone.utc) - timedelta(days=2)
    payload = dict(
        _INVASIVE,
        photo_url="https://example.org/knotweed.jpg",
        authored_at=authored.isoformat(),
    )

    body = client.post("/reports", json=payload, headers=_auth_headers(str(uuid.uuid4()))).json()

    assert body["photo_url"] == "https://example.org/knotweed.jpg"
    stored = datetime.fromisoformat(body["timestamp"]).replace(tzinfo=timezone.utc)
    assert abs((stored - authored).total_seconds()) < 5


def test_animals_stays_a_separate_type(client):
    """The two are deliberately distinct - animals is a safety encounter,
    invasive_species an ecological observation. Adding one must not have
    merged or displaced the other."""
    payload = {"type": "animals", "reporter_type": "thru", "lat": 37.9, "lon": -79.1}

    body = client.post("/reports", json=payload, headers=_auth_headers(str(uuid.uuid4()))).json()

    assert body["type"] == "animals"
