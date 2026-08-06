"""Tests for the `/reports` router - community condition reports.

See ../../features/REPORT_A_PROBLEM.md for the feature this mirrors. The
two server-controlled fields (`visibility`, `severity`) and the
server-authored `timestamp` are the load-bearing behaviors here - none of
them can be set or overridden by whatever a client sends in the request
body, only derived/assigned server-side.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.profile import Profile, Role
from app.models.report import Report, ReporterType, ReportStatus, ReportType, Visibility
from tests.tokens import auth_headers

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
    response = client.post("/reports", json=payload, headers=auth_headers(user_id))
    after = datetime.now(timezone.utc)

    assert response.status_code == 201
    body = response.json()
    stored_timestamp = datetime.fromisoformat(body["timestamp"]).replace(tzinfo=timezone.utc)

    assert stored_timestamp.year != 1999
    assert before - timedelta(seconds=5) <= stored_timestamp <= after + timedelta(seconds=5)


def test_create_report_defaults_bad_hikers_type_to_internal_only_visibility(client):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, type="bad_hikers")

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["visibility"] == "internal_only"


@pytest.mark.parametrize("report_type", ["blowdown", "trash", "flooding", "shelter_repair", "animals"])
def test_create_report_defaults_the_other_five_types_to_public_visibility(client, report_type):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, type=report_type)

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["visibility"] == "public"


def test_create_report_ignores_a_client_supplied_severity_field(client):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, severity="serious")

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["severity"] == "normal"


def test_public_list_reports_excludes_internal_only_reports(client, db_session):
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    # Both verified, so the only thing separating them in the result is
    # visibility - which is what this test is about. Before the moderation
    # gate existed these were left at the default `submitted` and still
    # appeared, so the test passed while proving less than it looked like.
    public_report = Report(
        reporter_id=reporter.id,
        type=ReportType.trash,
        reporter_type=ReporterType.day,
        visibility=Visibility.public,
        status=ReportStatus.verified,
    )
    internal_report = Report(
        reporter_id=reporter.id,
        type=ReportType.bad_hikers,
        reporter_type=ReporterType.day,
        visibility=Visibility.internal_only,
        status=ReportStatus.verified,
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
        status=ReportStatus.verified,
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
    owner_response = client.get(f"/reports/{internal_report.id}", headers=auth_headers(user_id))

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

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["timestamp"]).replace(tzinfo=timezone.utc)
    assert abs((stored - authored).total_seconds()) < 5


def test_create_report_defaults_the_timestamp_to_now_when_authored_at_is_omitted(client):
    user_id = str(uuid.uuid4())
    before = datetime.now(timezone.utc)

    response = client.post("/reports", json=_VALID_PAYLOAD, headers=auth_headers(user_id))

    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["timestamp"]).replace(tzinfo=timezone.utc)
    assert stored >= before - timedelta(seconds=5)


def test_create_report_records_received_at_as_server_time_not_the_clients_claim(client):
    user_id = str(uuid.uuid4())
    authored = datetime.now(timezone.utc) - timedelta(days=3)
    payload = dict(_VALID_PAYLOAD, authored_at=authored.isoformat())
    before = datetime.now(timezone.utc)

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

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

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

    assert response.status_code == 422


def test_create_report_tolerates_small_clock_skew_on_authored_at(client):
    # Phone clocks drift; a minute ahead is skew, not tampering.
    user_id = str(uuid.uuid4())
    payload = dict(
        _VALID_PAYLOAD,
        authored_at=(datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
    )

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

    assert response.status_code == 201


def test_an_outbox_flush_keeps_each_reports_own_authored_at(client):
    """TESTING.md item 13's server-side half: three reports written offline
    at different times, all synced in one burst, keep their own times."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id)
    authored = [datetime.now(timezone.utc) - timedelta(days=d) for d in (5, 3, 1)]

    for when in authored:
        response = client.post(
            "/reports",
            json=dict(_VALID_PAYLOAD, authored_at=when.isoformat()),
            headers=headers,
        )
        assert response.status_code == 201

    # Read back as the reporter. A just-flushed report is `submitted` and so
    # is not public yet, but its own author sees it - which is the case this
    # test needs anyway: an outbox flush is followed by the reporter looking
    # at what they just sent, not by a stranger doing so.
    listed = client.get("/reports", headers=headers).json()
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
    response = client.post("/reports", json=_INVASIVE, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    assert response.json()["type"] == "invasive_species"


def test_invasive_species_is_public_like_every_other_condition_type(client):
    """Nothing in an invasive report identifies a person, so none of the
    bad_hikers reasoning for internal_only applies."""
    body = client.post("/reports", json=_INVASIVE, headers=auth_headers(str(uuid.uuid4()))).json()

    assert body["visibility"] == Visibility.public.value


def test_invasive_species_appears_in_the_public_report_list_once_verified(client, db_session):
    """Public like every other condition type - but public still means
    moderated first, which is the one thing it does inherit from them."""
    moderator = Profile(id=str(uuid.uuid4()), role=Role.club_admin, display_name="Mod")
    db_session.add(moderator)
    db_session.commit()

    created = client.post("/reports", json=_INVASIVE, headers=auth_headers(str(uuid.uuid4()))).json()

    assert [r for r in client.get("/reports").json() if r["type"] == "invasive_species"] == []

    client.post(f"/reports/{created['id']}/verify", json={}, headers=auth_headers(moderator.id))

    listed = [r for r in client.get("/reports").json() if r["type"] == "invasive_species"]
    assert len(listed) == 1


def test_invasive_species_can_be_verified_unlike_a_thanks(client, db_session):
    """There IS something to verify about a species sighting, so it uses the
    normal moderation queue - the exception carved out for `thanks` must not
    have widened to cover every new type."""
    moderator = Profile(id=str(uuid.uuid4()), role=Role.club_admin, display_name="Mod")
    db_session.add(moderator)
    db_session.commit()

    created = client.post("/reports", json=_INVASIVE, headers=auth_headers(str(uuid.uuid4()))).json()
    response = client.post(
        f"/reports/{created['id']}/verify",
        json={"severity": "normal"},
        headers=auth_headers(moderator.id),
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

    body = client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4()))).json()

    assert body["photo_url"] == "https://example.org/knotweed.jpg"
    stored = datetime.fromisoformat(body["timestamp"]).replace(tzinfo=timezone.utc)
    assert abs((stored - authored).total_seconds()) < 5


def test_animals_stays_a_separate_type(client):
    """The two are deliberately distinct - animals is a safety encounter,
    invasive_species an ecological observation. Adding one must not have
    merged or displaced the other."""
    payload = {"type": "animals", "reporter_type": "thru", "lat": 37.9, "lon": -79.1}

    body = client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4()))).json()

    assert body["type"] == "animals"


# --- The moderation gate -------------------------------------------------
#
# REPORT_A_PROBLEM.md's "Architecture fit": reports are "submitted-by-many-
# people data that needs moderation before anything becomes visible to other
# hikers". That sentence is the stated reason a live backend is in v1 MVP at
# all, and until these tests existed nothing held the router to it - the
# filter was `status != dismissed`, which let every unmoderated report
# straight through to anyone.


def _verified_and_submitted_reports(db_session):
    """One report either side of the gate, from the same reporter."""
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()

    submitted = Report(
        reporter_id=reporter.id,
        type=ReportType.blowdown,
        reporter_type=ReporterType.thru,
        visibility=Visibility.public,
        status=ReportStatus.submitted,
    )
    verified = Report(
        reporter_id=reporter.id,
        type=ReportType.blowdown,
        reporter_type=ReporterType.thru,
        visibility=Visibility.public,
        status=ReportStatus.verified,
    )
    db_session.add_all([submitted, verified])
    db_session.commit()
    return reporter, submitted, verified


def test_public_list_hides_a_report_no_one_has_moderated_yet(client, db_session):
    _reporter, submitted, verified = _verified_and_submitted_reports(db_session)

    ids = [r["id"] for r in client.get("/reports").json()]

    assert verified.id in ids
    assert submitted.id not in ids


def test_getting_an_unmoderated_report_by_id_is_a_404_for_a_stranger(client, db_session):
    """The detail endpoint had the same hole as the list, which is why both
    now read the same constant: knowing the id was enough to read a report
    nobody had looked at."""
    _reporter, submitted, _verified = _verified_and_submitted_reports(db_session)

    response = client.get(f"/reports/{submitted.id}", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 404


def test_a_reporter_still_sees_their_own_report_while_it_waits(client, db_session):
    """Otherwise "Waiting" (client/src/lib/reportStatus.ts) has nothing to
    appear on, and a report would vanish from the app between being
    submitted and being verified."""
    reporter, submitted, _verified = _verified_and_submitted_reports(db_session)

    ids = [r["id"] for r in client.get("/reports", headers=auth_headers(reporter.id)).json()]

    assert submitted.id in ids


def test_a_resolved_report_stays_public(client, db_session):
    """It was verified once and reads as "Fixed" - a blowdown someone has
    since cleared is information, not noise."""
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add(reporter)
    db_session.commit()
    resolved = Report(
        reporter_id=reporter.id,
        type=ReportType.blowdown,
        reporter_type=ReporterType.thru,
        visibility=Visibility.public,
        status=ReportStatus.resolved,
    )
    db_session.add(resolved)
    db_session.commit()

    assert resolved.id in [r["id"] for r in client.get("/reports").json()]


def test_a_signed_in_stranger_sees_no_more_than_an_anonymous_one(client, db_session):
    """Sending a token must widen the result only by the caller's OWN
    reports - not by anything belonging to anyone else."""
    _reporter, submitted, verified = _verified_and_submitted_reports(db_session)

    ids = [r["id"] for r in client.get("/reports", headers=auth_headers(str(uuid.uuid4()))).json()]

    assert ids == [verified.id]
    assert submitted.id not in ids


# --- Idempotency (#243) --------------------------------------------------
#
# The failure this exists for is not exotic: the request commits here, the
# connection drops before the 201 gets back to a phone with one bar, the
# client's send throws, the item stays in the outbox, and the next flush
# files the same blowdown again. The outbox has always minted a stable UUID
# per item and documented it as "stable across retries, so a resend is
# recognisably the same report" - it just had nowhere to send it.


def test_a_resent_report_does_not_file_a_second_copy(client):
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id)
    report_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, id=report_id)

    first = client.post("/reports", json=payload, headers=headers)
    second = client.post("/reports", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"] == report_id
    assert len(client.get("/reports", headers=headers).json()) == 1


def test_a_resend_returns_the_stored_report_not_the_resent_one(client):
    """A retry carries the same body, but the stored row is what counts -
    a moderator may already have verified it between the two attempts."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id)
    report_id = str(uuid.uuid4())

    client.post("/reports", json=dict(_VALID_PAYLOAD, id=report_id), headers=headers)
    resent = client.post(
        "/reports",
        json=dict(_VALID_PAYLOAD, id=report_id, note="a different note"),
        headers=headers,
    )

    assert resent.status_code == 200
    assert resent.json()["note"] == _VALID_PAYLOAD["note"]


def test_an_id_belonging_to_someone_else_is_refused(client):
    """Refused rather than returned. Handing back another person's report
    would make a guessed UUID a way to read one - and for `bad_hikers`, a
    way to read an incident note about a named individual."""
    report_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, id=report_id)
    client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4())))

    response = client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 409


def test_an_omitted_id_still_works_and_is_server_assigned(client):
    """The same fallback `authored_at` gets from the server clock. A field
    the server can supply itself should not be a 422 waiting to happen."""
    response = client.post("/reports", json=_VALID_PAYLOAD, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    assert response.json()["id"]


def test_two_reports_without_ids_are_still_two_reports(client):
    """Idempotency keys off a supplied id, and must not accidentally
    deduplicate a hiker who really did report two blowdowns."""
    headers = auth_headers(str(uuid.uuid4()))

    first = client.post("/reports", json=_VALID_PAYLOAD, headers=headers)
    second = client.post("/reports", json=_VALID_PAYLOAD, headers=headers)

    assert first.json()["id"] != second.json()["id"]
    assert len(client.get("/reports", headers=headers).json()) == 2
