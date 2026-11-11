"""A survey pass: started, finished normally, finished early with where it ended.

#1991 — A survey pass records where a walk really started and ended, including
when it ended early.

Who may call either route is test_org_permission_matrix.py's job. This file
holds the outbox's contract - a start or a finish sent twice is one write -
and what a pass records: the trail must be the club's, each end is a pair or
nothing, and a finish happens once and never before its start.
"""

import uuid

import pytest

from app.core.time import utc_now
from app.models.club import OrgState
from app.models.inventory import InventoryClubSettings, InventoryEnrollment, InventoryPass, PassState
from app.models.org_registry import OrgTrail
from tests.factories import make_org, make_profile, make_section
from tests.tokens import auth_headers


def _volunteer(db_session, org):
    person = make_profile(db_session)
    db_session.add(
        InventoryEnrollment(
            club_id=org.id, person_id=person.id, waiver_version="2026-1", typed_name="Pat R.", training_completed_at=utc_now()
        )
    )
    db_session.commit()
    return person


@pytest.fixture
def survey(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    db_session.add(InventoryClubSettings(club_id=org.id, waiver_text="Words.", waiver_version="2026-1"))
    db_session.commit()
    trail_id = make_section(db_session, org).trail_id
    return {
        "org": org,
        "trail_id": trail_id,
        "volunteer": _volunteer(db_session, org),
        "url": f"/clubs/{org.slug}/inventory/passes",
    }


def _start(**changes):
    return {
        "id": str(uuid.uuid4()),
        "started_at": "2026-11-02T08:00:00-05:00",
        "from_lat": 41.4321,
        "from_lon": -73.8765,
        **changes,
    }


def _post(client, survey, body, person=None):
    return client.post(survey["url"], json=body, headers=auth_headers((person or survey["volunteer"]).id))


def _patch(client, survey, pass_id, body, person=None):
    return client.patch(f"{survey['url']}/{pass_id}", json=body, headers=auth_headers((person or survey["volunteer"]).id))


def _started(client, survey, **changes):
    body = _start(trail_id=survey["trail_id"], **changes)
    response = _post(client, survey, body)
    assert response.status_code == 201, response.text
    return body["id"]


# --- Starting ----------------------------------------------------------------


def test_a_pass_starts_in_progress_where_the_volunteer_stood(client, survey, db_session):
    body = _start(trail_id=survey["trail_id"], note="North end, from the Route 9 lot.")

    response = _post(client, survey, body)

    assert response.status_code == 201
    out = response.json()
    assert out["id"] == body["id"]
    assert out["state"] == "in_progress"
    assert (out["from_lat"], out["from_lon"]) == (41.4321, -73.8765)
    assert out["started_at"] == "2026-11-02T13:00:00Z"
    assert (out["finished_at"], out["to_lat"], out["to_lon"], out["ended_early"]) == (None, None, None, False)
    row = db_session.get(InventoryPass, body["id"])
    assert (row.club_id, row.volunteer_id, row.trail_id) == (
        survey["org"].id,
        survey["volunteer"].id,
        survey["trail_id"],
    )


def test_a_pass_started_with_no_fix_records_no_start_point(client, survey):
    body = _start(trail_id=survey["trail_id"])
    del body["from_lat"], body["from_lon"]

    response = _post(client, survey, body)

    assert response.status_code == 201
    assert (response.json()["from_lat"], response.json()["from_lon"]) == (None, None)


def test_the_same_start_sent_twice_is_one_pass(client, survey, db_session):
    body = _start(trail_id=survey["trail_id"])

    first = _post(client, survey, body)
    second = _post(client, survey, {**body, "note": "a changed copy"})

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json() == first.json()
    assert db_session.query(InventoryPass).count() == 1


def test_a_late_retry_of_the_start_does_not_reopen_a_finished_walk(client, survey):
    pass_id = _started(client, survey)
    assert _patch(client, survey, pass_id, {"finished_at": "2026-11-02T11:00:00-05:00"}).status_code == 200

    retry = _post(client, survey, _start(id=pass_id, trail_id=survey["trail_id"]))

    assert retry.status_code == 200
    assert retry.json()["state"] == "completed"


def test_somebody_elses_walk_id_is_refused_without_saying_whose(client, survey, db_session):
    pass_id = _started(client, survey)
    other = _volunteer(db_session, survey["org"])

    response = _post(client, survey, _start(id=pass_id, trail_id=survey["trail_id"]), person=other)

    assert response.status_code == 409
    assert response.json()["detail"] == "That walk id is already taken"


def test_a_trail_of_another_club_is_refused(client, survey, db_session):
    elsewhere = make_org(db_session, slug="another-trail-club", state=OrgState.claimed)
    their_trail = make_section(db_session, elsewhere).trail_id
    assert db_session.get(OrgTrail, their_trail) is not None

    response = _post(client, survey, _start(trail_id=their_trail))

    assert response.status_code == 422
    assert response.json()["detail"] == "That trail is not one of this organization's"


@pytest.mark.parametrize(
    "changes",
    [
        {"from_lat": 41.4321, "from_lon": None},
        {"from_lat": 91.0},
        {"from_lon": -181.0},
        {"started_at": "2999-01-01T00:00:00Z"},
    ],
)
def test_a_start_that_is_half_a_point_off_the_globe_or_in_the_future_is_refused(client, survey, changes):
    response = _post(client, survey, _start(trail_id=survey["trail_id"], **changes))

    assert response.status_code == 422


# --- Finishing ---------------------------------------------------------------


def test_a_walk_finished_normally_records_where_it_ended(client, survey):
    pass_id = _started(client, survey)

    response = _patch(
        client, survey, pass_id, {"finished_at": "2026-11-02T11:30:00-05:00", "to_lat": 41.4519, "to_lon": -73.8611}
    )

    assert response.status_code == 200
    out = response.json()
    assert out["state"] == "completed"
    assert out["finished_at"] == "2026-11-02T16:30:00Z"
    assert (out["to_lat"], out["to_lon"], out["ended_early"]) == (41.4519, -73.8611, False)


def test_a_walk_finished_early_keeps_the_point_the_volunteer_placed(client, survey, db_session):
    pass_id = _started(client, survey)

    response = _patch(
        client,
        survey,
        pass_id,
        {"finished_at": "2026-11-02T09:10:00-05:00", "to_lat": 41.4377, "to_lon": -73.8702, "ended_early": True},
    )

    assert response.status_code == 200
    row = db_session.get(InventoryPass, pass_id)
    db_session.refresh(row)
    assert (row.to_lat, row.to_lon, row.ended_early, row.state) == (41.4377, -73.8702, True, PassState.completed)


def test_a_walk_finished_with_no_fix_and_nothing_placed_has_an_unknown_end(client, survey):
    pass_id = _started(client, survey)

    response = _patch(client, survey, pass_id, {"finished_at": "2026-11-02T09:10:00-05:00", "ended_early": True})

    assert response.status_code == 200
    assert (response.json()["to_lat"], response.json()["to_lon"]) == (None, None)


def test_the_same_finish_sent_twice_answers_the_walk_unchanged(client, survey):
    pass_id = _started(client, survey)
    finish = {"finished_at": "2026-11-02T11:30:00-05:00", "to_lat": 41.4519, "to_lon": -73.8611}

    first = _patch(client, survey, pass_id, finish)
    second = _patch(client, survey, pass_id, finish)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == first.json()


def test_a_different_finish_of_a_finished_walk_is_refused(client, survey):
    """The first finish is what the volunteer said when they stopped; a stale
    copy on the phone must not rewrite it."""
    pass_id = _started(client, survey)
    assert _patch(client, survey, pass_id, {"finished_at": "2026-11-02T11:30:00-05:00"}).status_code == 200

    response = _patch(client, survey, pass_id, {"finished_at": "2026-11-02T09:10:00-05:00", "ended_early": True})

    assert response.status_code == 409
    assert response.json()["detail"] == "That walk is already finished"


def test_a_finish_before_the_start_is_refused(client, survey):
    pass_id = _started(client, survey)

    response = _patch(client, survey, pass_id, {"finished_at": "2026-11-02T07:59:00-05:00"})

    assert response.status_code == 422
    assert response.json()["detail"] == "A walk cannot finish before it started"


def test_another_volunteers_walk_cannot_be_finished_and_looks_like_no_walk(client, survey, db_session):
    pass_id = _started(client, survey)
    other = _volunteer(db_session, survey["org"])

    theirs = _patch(client, survey, pass_id, {"finished_at": "2026-11-02T11:30:00-05:00"}, person=other)
    nobodys = _patch(client, survey, str(uuid.uuid4()), {"finished_at": "2026-11-02T11:30:00-05:00"}, person=other)

    assert (theirs.status_code, nobodys.status_code) == (404, 404)
    assert theirs.json() == nobodys.json()


@pytest.mark.parametrize(
    "finish",
    [
        {"finished_at": "2026-11-02T11:30:00Z", "to_lat": 41.45},
        {"finished_at": "2026-11-02T11:30:00Z", "to_lat": 41.45, "to_lon": 200.0},
        {"finished_at": "2999-01-01T00:00:00Z"},
    ],
)
def test_a_finish_that_is_half_a_point_off_the_globe_or_in_the_future_is_refused(client, survey, finish):
    pass_id = _started(client, survey)

    assert _patch(client, survey, pass_id, finish).status_code == 422
