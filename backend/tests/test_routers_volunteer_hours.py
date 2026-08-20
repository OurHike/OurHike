"""Tests for the `/volunteer-hours` router (VOLUNTEERING.md §4, #761).

What these hold: the record is private (no anonymous read anywhere), hours
are bounded claims (positive, one day's worth, never future-dated), the
state machine is claimed -> confirmed|disputed with the audit pair set the
way every moderated resource here sets it, and the maintainer's 2026-08-20
decision - claimed counts until disputed - is a DISPLAY rule, so the wire
carries every state labeled and no endpoint invents a total.
"""

import uuid
from datetime import date, timedelta

from app.models.profile import Role
from app.models.volunteer_hours import VolunteerHoursRecord
from tests.factories import make_profile
from tests.tokens import auth_headers

_VALID_PAYLOAD = {
    "worked_on": "2026-08-18",
    "hours": 5.5,
    "activity": "maintenance",
    "note": "Cleared four blowdowns south of the gap.",
    "mile": 1402.3,
}


def _log(client, user_id, **overrides):
    return client.post(
        "/volunteer-hours",
        json={**_VALID_PAYLOAD, **overrides},
        headers=auth_headers(user_id),
    )


def test_logging_requires_authentication(client):
    assert client.post("/volunteer-hours", json=_VALID_PAYLOAD).status_code == 401


def test_a_logged_day_is_born_claimed(client):
    response = _log(client, str(uuid.uuid4()))

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "claimed"
    assert body["confirmed_at"] is None


def test_logging_is_idempotent_on_id(client, db_session):
    user_id = str(uuid.uuid4())
    record_id = str(uuid.uuid4())

    first = _log(client, user_id, id=record_id)
    second = _log(client, user_id, id=record_id)

    assert first.status_code == 201
    assert second.status_code == 200
    assert db_session.query(VolunteerHoursRecord).count() == 1


def test_an_id_belonging_to_someone_else_is_refused(client):
    record_id = str(uuid.uuid4())
    assert _log(client, str(uuid.uuid4()), id=record_id).status_code == 201

    assert _log(client, str(uuid.uuid4()), id=record_id).status_code == 409


def test_hours_are_bounded_claims(client):
    user_id = str(uuid.uuid4())

    zero = _log(client, user_id, hours=0)
    negative = _log(client, user_id, hours=-2)
    a_week_in_a_day = _log(client, user_id, hours=40)
    tomorrow = _log(client, user_id, worked_on=(date.today() + timedelta(days=3)).isoformat())

    assert zero.status_code == 422
    assert negative.status_code == 422
    assert a_week_in_a_day.status_code == 422
    assert tomorrow.status_code == 422


def test_mine_is_the_callers_own_logbook_and_nobody_elses(client):
    author = str(uuid.uuid4())
    stranger = str(uuid.uuid4())
    assert _log(client, author).status_code == 201

    own = client.get("/volunteer-hours/mine", headers=auth_headers(author)).json()
    strangers = client.get("/volunteer-hours/mine", headers=auth_headers(stranger)).json()
    anonymous = client.get("/volunteer-hours/mine")

    assert len(own) == 1
    assert own[0]["note"] == "Cleared four blowdowns south of the gap."
    assert strangers == []
    assert anonymous.status_code == 401


def test_confirm_and_dispute_are_club_actions_with_an_audit_pair(client, db_session):
    volunteer = str(uuid.uuid4())
    admin = make_profile(db_session, Role.club_admin)
    record_id = _log(client, volunteer).json()["id"]

    hiker_confirm = client.post(f"/volunteer-hours/{record_id}/confirm", headers=auth_headers(volunteer))
    assert hiker_confirm.status_code == 403

    confirmed = client.post(f"/volunteer-hours/{record_id}/confirm", headers=auth_headers(admin.id)).json()
    assert confirmed["state"] == "confirmed"
    assert confirmed["confirmed_at"] is not None

    disputed = client.post(f"/volunteer-hours/{record_id}/dispute", headers=auth_headers(admin.id)).json()
    assert disputed["state"] == "disputed"

    # The record survives a dispute, and stays visible to its volunteer - a
    # disagreement to take up with the club, not an erasure.
    own = client.get("/volunteer-hours/mine", headers=auth_headers(volunteer)).json()
    assert [row["state"] for row in own] == ["disputed"]


def test_the_queue_lists_what_still_waits_on_a_club(client, db_session):
    admin = make_profile(db_session, Role.maintainer)
    volunteer = str(uuid.uuid4())
    waiting_id = _log(client, volunteer, id=str(uuid.uuid4())).json()["id"]
    settled_id = _log(client, volunteer, id=str(uuid.uuid4()), worked_on="2026-08-17").json()["id"]
    assert client.post(f"/volunteer-hours/{settled_id}/confirm", headers=auth_headers(admin.id)).status_code == 200

    queue = client.get("/volunteer-hours/queue", headers=auth_headers(admin.id)).json()
    hiker_view = client.get("/volunteer-hours/queue", headers=auth_headers(volunteer))

    assert [row["id"] for row in queue] == [waiting_id]
    assert hiker_view.status_code == 403


def test_an_unknown_club_is_named_rather_than_a_500(client):
    response = _log(client, str(uuid.uuid4()), club_id="no-such-club")

    assert response.status_code == 422
    assert "club_id" in response.json()["detail"]
