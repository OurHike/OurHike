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
from pydantic import ValidationError

from app.models.profile import Profile, Role
from app.models.report import Report, ReporterType, ReportStatus, ReportType, Visibility
from app.schemas.report import ReportCreate
from tests.factories import make_profile
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
    stored_timestamp = datetime.fromisoformat(body["timestamp"])

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
    reporter = make_profile(db_session, Role.hiker)

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
    reporter = make_profile(db_session, Role.hiker)

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
    stored = datetime.fromisoformat(response.json()["timestamp"])
    assert abs((stored - authored).total_seconds()) < 5


def test_create_report_defaults_the_timestamp_to_now_when_authored_at_is_omitted(client):
    user_id = str(uuid.uuid4())
    before = datetime.now(timezone.utc)

    response = client.post("/reports", json=_VALID_PAYLOAD, headers=auth_headers(user_id))

    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["timestamp"])
    assert stored >= before - timedelta(seconds=5)


def test_create_report_records_received_at_as_server_time_not_the_clients_claim(client):
    user_id = str(uuid.uuid4())
    authored = datetime.now(timezone.utc) - timedelta(days=3)
    payload = dict(_VALID_PAYLOAD, authored_at=authored.isoformat())
    before = datetime.now(timezone.utc)

    response = client.post("/reports", json=payload, headers=auth_headers(user_id))

    received = datetime.fromisoformat(response.json()["received_at"])
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
    stored = sorted(datetime.fromisoformat(r["timestamp"]) for r in listed)

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
    moderator = make_profile(db_session, Role.club_admin, display_name="Mod")

    created = client.post("/reports", json=_INVASIVE, headers=auth_headers(str(uuid.uuid4()))).json()

    assert [r for r in client.get("/reports").json() if r["type"] == "invasive_species"] == []

    client.post(f"/reports/{created['id']}/verify", json={}, headers=auth_headers(moderator.id))

    listed = [r for r in client.get("/reports").json() if r["type"] == "invasive_species"]
    assert len(listed) == 1


def test_invasive_species_can_be_verified_unlike_a_thanks(client, db_session):
    """There IS something to verify about a species sighting, so it uses the
    normal moderation queue - the exception carved out for `thanks` must not
    have widened to cover every new type."""
    moderator = make_profile(db_session, Role.club_admin, display_name="Mod")

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
    stored = datetime.fromisoformat(body["timestamp"])
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
    reporter = make_profile(db_session, Role.hiker)

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
    reporter = make_profile(db_session, Role.hiker)
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


# --- The idempotency key is a trust boundary (#265) -----------------------
#
# `id` becomes the row's PRIMARY KEY, and moderation addresses a report by
# URL path segment (`POST /reports/{report_id}/verify`). An unconstrained
# string let a caller choose an id no route could ever match, and with no
# delete endpoint anywhere the row was unreachable forever - so anyone with
# an account could park un-clearable `bad_hikers` notes about named people
# in the queue that closures and serious warnings share.


@pytest.mark.parametrize(
    "bad_id",
    [
        "a/b",  # extra path segment: verify and dismiss both 404
        "",  # empty segment: same
        "..",  # traversal-shaped: same
        "x?y",  # query separator: 405
        "#frag",  # fragment: 422 at the routing layer
        "A" * 300,  # unbounded length
        "not-a-uuid",
        "12345",
    ],
)
def test_an_id_that_is_not_a_uuid_is_refused(client, bad_id):
    payload = dict(_VALID_PAYLOAD, id=bad_id)

    response = client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 422


def test_a_refused_id_files_nothing(client):
    """The point is not the status code, it is that nothing reaches the
    database - an unreachable row cannot be cleaned up afterwards."""
    headers = auth_headers(str(uuid.uuid4()))

    client.post("/reports", json=dict(_VALID_PAYLOAD, id="a/b"), headers=headers)

    assert client.get("/reports", headers=headers).json() == []


def test_a_moderator_can_always_reach_a_report_that_was_accepted(client, db_session):
    """The property the validation exists to protect, asserted end to end
    rather than inferred from the 422s above."""
    moderator = make_profile(db_session, Role.club_admin, display_name="Mod")
    created = client.post(
        "/reports",
        json=dict(_VALID_PAYLOAD, type="bad_hikers", id=str(uuid.uuid4())),
        headers=auth_headers(str(uuid.uuid4())),
    ).json()

    dismissed = client.post(f"/reports/{created['id']}/dismiss", headers=auth_headers(moderator.id))

    assert dismissed.status_code == 200


def test_the_same_uuid_in_a_different_case_is_the_same_report(client):
    """The column is a String, so `{ID}` and `{id}` would otherwise be two
    primary keys - and a retry that re-cased the id would file a duplicate,
    defeating the whole point."""
    headers = auth_headers(str(uuid.uuid4()))
    report_id = str(uuid.uuid4())

    first = client.post("/reports", json=dict(_VALID_PAYLOAD, id=report_id), headers=headers)
    second = client.post("/reports", json=dict(_VALID_PAYLOAD, id=report_id.upper()), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/reports", headers=headers).json()) == 1


def test_losing_the_insert_race_returns_the_stored_report_not_a_500(client, monkeypatch):
    """Two concurrent sends of the same id both see "not filed yet" and both
    insert. That is not a rare interleaving - it is exactly what the retry
    path produces - and losing it used to surface as a 500 from the one
    endpoint whose entire promise is that sending twice is safe.

    Simulated by making the pre-check miss once, which is precisely what the
    losing request observes."""
    from app.routers import reports as reports_router

    headers = auth_headers(str(uuid.uuid4()))
    report_id = str(uuid.uuid4())
    first = client.post("/reports", json=dict(_VALID_PAYLOAD, id=report_id), headers=headers)
    assert first.status_code == 201

    real = reports_router._already_filed
    calls = {"n": 0}

    def blind_once(db, rid, user):
        calls["n"] += 1
        # The pre-check runs first and sees nothing; the post-IntegrityError
        # recovery uses the real lookup.
        return None if calls["n"] == 1 else real(db, rid, user)

    monkeypatch.setattr(reports_router, "_already_filed", blind_once)

    second = client.post("/reports", json=dict(_VALID_PAYLOAD, id=report_id), headers=headers)

    assert second.status_code == 200
    assert second.json()["id"] == report_id
    assert calls["n"] == 2
    assert len(client.get("/reports", headers=headers).json()) == 1


# --- What leaves the server, and to whom (#252) ---------------------------
#
# `ReportOut` used to serialise `reporter_id` - a stable account UUID - to
# anonymous callers alongside a trail position and a time. Group by it and a
# hiker's route down the corridor falls out, with curl and no account.
# features/IDENTITY_AND_PRIVACY.md names exactly that linkability.
#
# The decision is per (row, viewer), not per route, which is why there is one
# schema with a `for_viewer` constructor rather than a public/private pair:
# `GET /reports` with a token returns the caller's own rows AND other people's
# public rows in ONE response. A per-route split gets that case silently
# wrong, so it has a test of its own below.


def _public_report(db_session, reporter_id: str, **overrides) -> Report:
    """A verified, public report by someone - the kind anyone can read."""
    report = Report(
        reporter_id=reporter_id,
        type=ReportType.blowdown,
        reporter_type="thru",
        visibility=Visibility.public,
        status=ReportStatus.verified,
        **overrides,
    )
    db_session.add(report)
    db_session.commit()
    return report


def test_anonymous_list_withholds_the_reporter_id(client, db_session):
    reporter = make_profile(db_session, Role.hiker)
    _public_report(db_session, reporter.id)

    body = client.get("/reports").json()

    assert len(body) == 1
    # Present and null, not absent: the field stays in the contract so a
    # client does not have to tell "withheld" from "this build is older".
    assert "reporter_id" in body[0]
    assert body[0]["reporter_id"] is None


def test_anonymous_detail_withholds_it_too(client, db_session):
    reporter = make_profile(db_session, Role.hiker)
    report = _public_report(db_session, reporter.id)

    body = client.get(f"/reports/{report.id}").json()

    assert body["reporter_id"] is None


def test_a_signed_in_stranger_is_still_a_stranger(client, db_session):
    """Having an account does not entitle you to somebody else's identity.

    The case a per-route split silently gets wrong: the route is
    authenticated, so a schema chosen by route would hand over everything.
    """
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    stranger_id = str(uuid.uuid4())
    db_session.add_all([reporter, Profile(id=stranger_id, role=Role.hiker)])
    db_session.commit()
    report = _public_report(db_session, reporter.id)

    body = client.get(f"/reports/{report.id}", headers=auth_headers(stranger_id)).json()

    assert body["reporter_id"] is None


def test_one_response_can_carry_both_answers_at_once(client, db_session):
    """The whole reason this is decided per row.

    A signed-in hiker's list contains their own report and a stranger's
    public one. The first must carry the id; the second must not.
    """
    mine = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    theirs = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    db_session.add_all([mine, theirs])
    db_session.commit()
    my_report = _public_report(db_session, mine.id)
    their_report = _public_report(db_session, theirs.id)

    body = client.get("/reports", headers=auth_headers(mine.id)).json()
    by_id = {row["id"]: row for row in body}

    assert by_id[my_report.id]["reporter_id"] == mine.id
    assert by_id[their_report.id]["reporter_id"] is None


def test_a_moderator_sees_who_filed_it(client, db_session):
    """The queue is unusable otherwise: deciding whether a `bad_hikers` note
    is abuse means knowing whether the same account filed six of them."""
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    maintainer_id = str(uuid.uuid4())
    db_session.add_all([reporter, Profile(id=maintainer_id, role=Role.maintainer)])
    db_session.commit()
    report = _public_report(db_session, reporter.id)

    body = client.get(f"/reports/{report.id}", headers=auth_headers(maintainer_id)).json()

    assert body["reporter_id"] == reporter.id


def test_a_maintainer_id_on_a_public_report_is_withheld_too(client, db_session):
    """The second leak, which the issue did not name.

    `create_report` copies `maintainer_id` and `club_id` from the request for
    EVERY report type, while `_visibility_for` forces `club_only` only for a
    `thanks`. So a `blowdown` carrying an arbitrary real profile id is
    `public` - `maintainer_id` was a second `reporter_id` that nobody had
    noticed, and dropping only the obvious one would have left it.
    """
    reporter = Profile(id=str(uuid.uuid4()), role=Role.hiker)
    named = Profile(id=str(uuid.uuid4()), role=Role.maintainer)
    db_session.add_all([reporter, named])
    db_session.commit()
    report = _public_report(db_session, reporter.id, maintainer_id=named.id)

    body = client.get(f"/reports/{report.id}").json()

    assert body["maintainer_id"] is None
    assert body["club_id"] is None


def test_the_receipt_time_is_withheld_as_well(client, db_session):
    """A second clock narrows "when was this person there" further than
    either alone, and nothing public reads it - the client's own
    `ReportSummary` does not even declare the field."""
    reporter = make_profile(db_session, Role.hiker)
    _public_report(db_session, reporter.id)

    assert client.get("/reports").json()[0]["received_at"] is None


def test_a_reporter_reading_their_own_report_still_gets_everything(client, db_session):
    """The nuance the fix had to preserve. "Waiting" needs something to
    appear on, and their own report is theirs to see in full."""
    reporter_id = str(uuid.uuid4())
    db_session.add(Profile(id=reporter_id, role=Role.hiker))
    db_session.commit()
    report = _public_report(db_session, reporter_id)

    body = client.get(f"/reports/{report.id}", headers=auth_headers(reporter_id)).json()

    assert body["reporter_id"] == reporter_id
    assert body["received_at"] is not None


def test_creating_a_report_returns_it_to_its_author_in_full(client):
    """The author is the caller by construction here, so this is the owner
    path - a 201 that withheld the id would be withholding it from the one
    person it belongs to."""
    reporter_id = str(uuid.uuid4())

    response = client.post("/reports", json=_VALID_PAYLOAD, headers=auth_headers(reporter_id))

    assert response.status_code == 201
    assert response.json()["reporter_id"] == reporter_id


def test_the_public_list_is_ordered_so_array_position_leaks_nothing(client, db_session):
    """The covert channel that survived withholding `received_at`.

    Unordered, this endpoint returned rows in whatever order Postgres
    happened to scan them - for a small table, heap order, which is
    insertion order. `jq 'to_entries'` then recovers the receipt ordering
    the response had just withheld. Worse: the client outbox flushes
    strictly serially, so one hiker's days-long backlog arrives as
    consecutive INSERTs and came back as a contiguous run of adjacent
    indices at positions advancing along the corridor - the reporter
    grouping this whole change exists to end, rebuilt out of array order.

    Asserted as "sorted by id" rather than "not insertion order", because
    the second is a property of a particular database's scan behaviour and
    the first is the thing the code promises.
    """
    reporter = make_profile(db_session, Role.hiker)
    for _ in range(5):
        _public_report(db_session, reporter.id)

    ids = [row["id"] for row in client.get("/reports").json()]

    assert len(ids) == 5
    assert ids == sorted(ids)


def _report_emitting_routes():
    """Every route in the REAL app that can put a ReportOut on the wire.

    Two signals, unioned, because either alone has a blind spot: a handler
    declaring `response_model=ReportOut` and returning the ORM row never
    mentions the schema in its body, and `GET /moderation/queue` declares
    `ModerationQueue` while nesting ReportOut inside it.

    The walk descends through `original_router`: this FastAPI version wraps
    each `include_router` in an `_IncludedRouter` rather than flattening, so
    `app.routes` alone reaches only `/health` and the docs.
    """
    import inspect

    from app.main import app

    def walk(routes):
        for route in routes:
            included = getattr(route, "original_router", None)
            if included is not None:
                yield from walk(included.routes)
                continue
            nested = getattr(route, "routes", None)
            if nested:
                yield from walk(nested)
            else:
                yield route

    for route in walk(app.routes):
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        source = inspect.getsource(endpoint)
        declared = str(getattr(route, "response_model", "") or "")
        if "ReportOut" in declared or "ReportOut" in source:
            yield route, source


def test_every_route_that_can_emit_a_report_goes_through_for_viewer():
    """The guard, and an honest account of what it can and cannot prove.

    Dropping `from_attributes` from ReportOut looks like it would make the
    leak impossible - `ReportOut.model_validate(row)` then raises - and it
    does not: FastAPI validates response models with
    `validate_python(value, from_attributes=True)` passed explicitly
    (fastapi/_compat/v2.py), so `response_model=ReportOut` would go on
    serialising the whole ORM row regardless. Measured against this repo,
    not assumed - which is why ReportOut keeps its `from_attributes` and
    says so, instead of carrying a comment claiming a protection it does
    not have.

    So nothing structural stops a seventh handler shipping `return report`.
    What this does instead is read the REAL route table - not a list kept
    here - and require every handler that can emit a ReportOut to name
    `for_viewer`. A route added later is caught because the app is the thing
    being read.
    """
    offenders = [
        f"{sorted(route.methods)} {route.path} -> {route.endpoint.__name__}"
        for route, source in _report_emitting_routes()
        if "for_viewer" not in source
    ]

    assert offenders == [], (
        "These handlers can emit a ReportOut without going through "
        "ReportOut.for_viewer, so they serialise the raw ORM row and hand "
        "reporter_id to whoever called them (#252):\n  " + "\n  ".join(offenders)
    )


def test_that_guard_is_actually_looking_at_something():
    """Guards the guard. A walk that failed to reach the routers - which is
    exactly what `app.routes` alone does here - would make the test above
    pass vacuously and for ever."""
    found = {route.path for route, _ in _report_emitting_routes()}

    assert "/reports" in found
    assert "/reports/{report_id}" in found
    # The nested case: this one declares ModerationQueue, not ReportOut.
    assert "/moderation/queue" in found
    assert len(found) >= 5


# --- The trail mile a report was written at (#244) -------------------------
#
# The form snapped the GPS fix to the centerline, rendered "mi 1,407.2" on
# screen, and then submitted `lat`/`lon` alone - so the one number the serious-
# warnings banner filters on was known at the moment it was thrown away, and
# unavailable to anything server-side ever after. It is a client claim like
# `authored_at`, for the same reason: this backend holds no centerline to
# derive one from.


def test_create_report_stores_the_mile_the_form_already_computed(client):
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, mile=1407.2)

    body = client.post("/reports", json=payload, headers=auth_headers(user_id)).json()

    assert body["mile"] == 1407.2


def test_a_report_without_a_mile_is_null_rather_than_zero(client):
    """Mile 0 is Springer Mountain, so it is not a stand-in for "unknown".

    An off-trail fix and a phone with no trail index downloaded both produce
    no mile, and a zero default would file both at the southern terminus -
    two thousand miles from where they happened.
    """
    user_id = str(uuid.uuid4())

    body = client.post("/reports", json=_VALID_PAYLOAD, headers=auth_headers(user_id)).json()

    assert body["mile"] is None


def test_the_mile_travels_back_out_on_the_public_list(client, db_session):
    """The banner reads this list, so a mile that only exists in the row is a
    mile the safety feature still cannot filter on."""
    reporter = make_profile(db_session, Role.hiker)
    db_session.add(
        Report(
            id=str(uuid.uuid4()),
            reporter_id=reporter.id,
            type=ReportType.blowdown,
            reporter_type=ReporterType.thru,
            lat=35.6,
            lon=-83.5,
            mile=1407.2,
            status=ReportStatus.verified,
            visibility=Visibility.public,
        )
    )
    db_session.commit()

    listed = client.get("/reports").json()

    assert [row["mile"] for row in listed] == [1407.2]


@pytest.mark.parametrize("bad", [-0.1, -1, -2197])
def test_a_negative_mile_is_refused(client, bad):
    """South of the southern terminus, which no snap returns.

    It would also sort into every route range that starts at mile 0 - so a
    bad value is not merely wrong, it is wrong in the direction of appearing
    on every hiker's banner.
    """
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, mile=bad)

    assert client.post("/reports", json=payload, headers=auth_headers(user_id)).status_code == 422


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_mile_that_is_not_a_number_is_refused(bad):
    """NaN is the dangerous one, and it fails quietly rather than loudly.

    Every `>=` and `<=` against NaN is false, so a serious warning carrying
    one is absent from every route range instead of misplaced in one - a
    safety warning that exists in the database and on no phone.

    **Tested on the schema rather than over HTTP, because HTTP cannot carry
    it.** These values only exist in JSON as the bare `NaN`/`Infinity` tokens
    Python's `json.dumps` emits, and FastAPI's body parser refuses those
    before any validator runs - as does `JSON.stringify`, which writes
    `null`. So the wire is already closed, and what this guards is the model
    itself: pydantic accepts inf and NaN as floats by default
    (`allow_inf_nan`), so anything constructing a `ReportCreate` in Python -
    a script, a future non-JSON transport, a test - would otherwise get one
    through.
    """
    with pytest.raises(ValidationError, match="real number"):
        ReportCreate(type="blowdown", reporter_type="thru", mile=bad)


def test_the_northern_end_of_the_trail_is_not_refused(client):
    """No upper bound, deliberately.

    The trail's length lives in the published centerline and moves as
    relocations land; a constant here would be a second copy of a number the
    pipeline owns, and it would start refusing real reports from Maine the
    first time the trail was re-measured longer.
    """
    user_id = str(uuid.uuid4())
    payload = dict(_VALID_PAYLOAD, mile=2197.4)

    assert client.post("/reports", json=payload, headers=auth_headers(user_id)).status_code == 201


def test_a_resent_report_keeps_the_mile_it_was_filed_with(client):
    """The idempotent retry path (#243) returns the STORED report, so this is
    really a check that the mile is on the stored one and not re-read from the
    resend - a phone that has since walked on would otherwise move the pin."""
    user_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    first = dict(_VALID_PAYLOAD, id=report_id, mile=1407.2)
    client.post("/reports", json=first, headers=auth_headers(user_id))

    resent = dict(_VALID_PAYLOAD, id=report_id, mile=1500.0)
    body = client.post("/reports", json=resent, headers=auth_headers(user_id)).json()

    assert body["mile"] == 1407.2
