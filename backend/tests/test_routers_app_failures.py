"""Tests for the `/app-failures` router (#848).

See ../../features/APP_FAILURE_REPORTS.md. What is worth testing here is not
that a POST stores a row - it is the three ways this endpoint deliberately
behaves unlike every other write in the backend, because each of them is a
decision somebody could reasonably undo without noticing what it was for:

  - **It accepts an anonymous caller.** Undo that and the hiker whose app
    just failed is asked to make an account first.
  - **It does not 422.** Undo that and an over-long note or a wrong phone
    clock does not bounce the request - it strands the report permanently in
    that phone's outbox (client/src/lib/api.ts, `permanentFailureReason`),
    which is the report never arriving at all.
  - **It never reads a row back.** Undo that and this table's contact
    details acquire a way out.
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.app_failure import AppFailure
from app.schemas.app_failure import SHORT_FIELD_MAX_CHARS, WHAT_HAPPENED_MAX_CHARS
from tests.factories import make_profile
from tests.tokens import auth_headers

MINIMAL = {"what_happened": "The map went blank and would not come back."}


def _stored(db_session, response) -> AppFailure:
    return db_session.get(AppFailure, response.json()["id"])


# --- who may file ---------------------------------------------------------


def test_a_signed_out_hiker_can_file(client, db_session):
    """The whole point. Every other write here needs an account; this one
    must not, because browsing the map never did and the person reporting
    that the app failed them is often somebody who never signed in."""
    response = client.post("/app-failures", json=MINIMAL)

    assert response.status_code == 201
    assert _stored(db_session, response).reporter_id is None


def test_a_signed_in_hiker_is_recorded_as_the_reporter(client, db_session):
    """Not required, and worth having: it is the second way to reach
    somebody when the contact detail they left turns out to be wrong."""
    profile = make_profile(db_session)

    response = client.post("/app-failures", json=MINIMAL, headers=auth_headers(profile.id))

    assert response.status_code == 201
    assert _stored(db_session, response).reporter_id == profile.id


def test_an_unusable_token_is_treated_as_no_token_rather_than_as_an_error(client, db_session):
    """An expired session must not cost somebody their report. The request
    works without an account at all, so a credential that cannot be used is
    the same situation as not sending one."""
    response = client.post(
        "/app-failures",
        json=MINIMAL,
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 201
    assert _stored(db_session, response).reporter_id is None


# --- what it stores -------------------------------------------------------


def test_it_stores_the_contact_detail_exactly_as_given(client, db_session):
    """Unparsed and unvalidated, which is the column's whole design: a
    hiker may leave an email, a phone number, or where they will be on
    Friday, and anything that constrained the shape would be a way of
    refusing one of those."""
    response = client.post(
        "/app-failures",
        json={**MINIMAL, "contact": "I'm at Standing Bear Fri — ask for Sparrow"},
    )

    assert _stored(db_session, response).contact == "I'm at Standing Bear Fri — ask for Sparrow"


def test_it_keeps_the_whole_report(client, db_session):
    response = client.post(
        "/app-failures",
        json={
            **MINIMAL,
            "whereabouts": "the ford below Fontana, about 4pm",
            "contact": "sparrow@example.com",
            "harms": ["lost", "water"],
            "build": "1.0.0 · 6e23f12",
            "was_offline": True,
        },
    )

    failure = _stored(db_session, response)
    assert failure.whereabouts == "the ford below Fontana, about 4pm"
    assert failure.harms == ["lost", "water"]
    assert failure.build == "1.0.0 · 6e23f12"
    assert failure.was_offline is True


def test_an_unanswered_harms_question_stays_distinguishable_from_an_unasked_one(client, db_session):
    """Empty is "none of these", stored as an empty list. It is a different
    fact from a row filed before the question existed, which is null."""
    response = client.post("/app-failures", json=MINIMAL)

    assert _stored(db_session, response).harms == []


def test_nobody_has_answered_a_report_the_moment_it_arrives(client, db_session):
    assert _stored(db_session, client.post("/app-failures", json=MINIMAL)).answered_at is None


# --- what it refuses to refuse -------------------------------------------


def test_an_over_long_report_is_cut_rather_than_refused(client, db_session):
    """The asymmetry this endpoint exists on: a 422 does not ask the hiker
    to try again, it marks the item permanently failed in their outbox. So
    somebody who wrote two thousand words about nearly walking off a ledge
    loses the tail, never the report."""
    response = client.post(
        "/app-failures",
        json={"what_happened": "x" * (WHAT_HAPPENED_MAX_CHARS + 500)},
    )

    assert response.status_code == 201
    assert len(_stored(db_session, response).what_happened) == WHAT_HAPPENED_MAX_CHARS


def test_an_over_long_contact_is_cut_rather_than_refused(client, db_session):
    response = client.post(
        "/app-failures",
        json={**MINIMAL, "contact": "c" * (SHORT_FIELD_MAX_CHARS + 50)},
    )

    assert response.status_code == 201
    assert len(_stored(db_session, response).contact) == SHORT_FIELD_MAX_CHARS


def test_a_harm_this_server_does_not_know_is_dropped_and_the_rest_kept(client, db_session):
    """An older server meeting a newer client keeps the four harms it
    understands rather than refusing the report over the fifth."""
    response = client.post(
        "/app-failures",
        json={**MINIMAL, "harms": ["lost", "eaten_by_a_bear", "hazard"]},
    )

    assert response.status_code == 201
    assert _stored(db_session, response).harms == ["lost", "hazard"]


def test_a_phone_with_a_wrong_clock_still_gets_through(client, db_session):
    """`POST /reports` refuses a future `authored_at`, and is right to: a
    backdated blowdown misleads a maintainer reading a queue by time.
    Nothing sorts this table by the hiker's claim, `received_at` is the
    server's own truth beside it, and refusing would lose the report."""
    ahead = datetime.now(timezone.utc) + timedelta(days=400)

    response = client.post(
        "/app-failures",
        json={**MINIMAL, "authored_at": ahead.isoformat()},
    )

    assert response.status_code == 201
    failure = _stored(db_session, response)
    assert failure.authored_at.year == ahead.year
    # The pair is what makes the wrong clock visible rather than believed.
    assert failure.received_at < failure.authored_at


def test_a_report_written_days_ago_keeps_the_day_it_was_written(client, db_session):
    """The ordinary case out here: written with no signal, flushed in town.
    A four-day-old failure must not read as today's."""
    written = datetime.now(timezone.utc) - timedelta(days=4)

    response = client.post(
        "/app-failures",
        json={**MINIMAL, "authored_at": written.isoformat()},
    )

    failure = _stored(db_session, response)
    assert (failure.received_at - failure.authored_at) > timedelta(days=3)


def test_a_report_that_says_nothing_at_all_is_still_refused(client):
    """The one thing that is not a report. `what_happened` is the only
    required field, and a body without it has nothing to store."""
    assert client.post("/app-failures", json={}).status_code == 422


# --- sending it twice -----------------------------------------------------


def test_resending_the_same_id_does_not_file_a_second_copy(client, db_session):
    """The classic one-bar failure: the request commits and its response
    never arrives, so the outbox sends again."""
    failure_id = str(uuid.uuid4())
    body = {**MINIMAL, "id": failure_id}

    first = client.post("/app-failures", json=body)
    second = client.post("/app-failures", json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == failure_id
    assert db_session.query(AppFailure).count() == 1


def test_a_colliding_id_from_someone_else_is_acknowledged_rather_than_refused(client, db_session):
    """`POST /reports` answers 409 here, because handing back somebody
    else's report would be a way to read it. There is nothing to read back
    from this endpoint - the acknowledgement carries the id the caller sent
    and an arrival time - and a 409 reaches a hiker's outbox as permanent."""
    profile = make_profile(db_session)
    failure_id = str(uuid.uuid4())

    client.post("/app-failures", json={**MINIMAL, "id": failure_id}, headers=auth_headers(profile.id))
    second = client.post("/app-failures", json={"what_happened": "different", "id": failure_id})

    assert second.status_code == 200
    assert db_session.query(AppFailure).count() == 1


# --- what it never does ---------------------------------------------------


def test_the_acknowledgement_says_nothing_about_what_was_stored(client):
    """Nothing here may echo a contact detail back. The reply is the id the
    caller already sent and the time it landed."""
    response = client.post(
        "/app-failures",
        json={**MINIMAL, "contact": "sparrow@example.com", "whereabouts": "mi 1407"},
    )

    assert set(response.json()) == {"id", "received_at"}
    assert "sparrow@example.com" not in response.text


def test_there_is_no_way_to_read_these_back(client, db_session):
    """The guarantee that keeps the contact details safe is that nothing
    serves them. A GET added later has to break this test first, which is
    the point at which somebody has to answer "who may read a stranger's
    phone number, and how is that checked"."""
    response = client.post("/app-failures", json={**MINIMAL, "contact": "sparrow@example.com"})
    failure_id = response.json()["id"]

    assert client.get("/app-failures").status_code in (404, 405)
    assert client.get(f"/app-failures/{failure_id}").status_code in (404, 405)
