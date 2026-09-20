"""Tests for `/workdays` - VOLUNTEERING.md phase D (#762).

The three worth reading first are the three the design says are most likely
to be got wrong:

- **A signup is an introduction, not an enrolment.** It is born `interested`,
  and the wire carries no way for a volunteer to say otherwise.
- **A mirrored workday's signup goes to the organization's own form**, and the
  refusal names where. Quietly collecting hands the org will never see is the
  failure that leaves somebody thinking they are on a roster.
- **Cancelling a signup is one tap and consequence-free**, and nothing counts
  how often anybody does it.
"""

import uuid
from datetime import date, timedelta

from app.models.club import OrgState
from app.models.work_project import ProjectSource, SignupMode, SignupState, WorkProjectSignup
from tests.factories import make_admin, make_org, make_profile, make_workday
from tests.tokens import auth_headers


def _org_with_admin(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    return org, admin


def test_a_workday_is_posted_by_somebody_who_runs_crews(client, db_session):
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/workdays",
        json={
            "title": "Clear blowdowns, Pine Meadow",
            "starts_on": (date.today() + timedelta(days=7)).isoformat(),
            "meet_point": "Reeves Meadow Visitor Center, 8am",
            "cap": 12,
        },
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "upcoming"
    assert response.json()["confirmed_count"] == 0


def test_a_single_day_workday_does_not_have_its_date_typed_twice(client, db_session):
    _, admin = _org_with_admin(db_session)
    day = (date.today() + timedelta(days=3)).isoformat()

    body = client.post(
        "/clubs/ramapo-trail-conference/workdays",
        json={"title": "Blaze painting", "starts_on": day},
        headers=auth_headers(admin.id),
    ).json()

    assert body["ends_on"] == day


def test_a_cap_of_zero_is_refused_because_it_is_not_a_cap(client, db_session):
    """An org that has not said is a different thing from one that said nobody."""
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/workdays",
        json={"title": "x", "starts_on": date.today().isoformat(), "cap": 0},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_a_mirrored_workday_has_to_say_where_its_signup_lives(client, db_session):
    """Without one the screen renders "sign up on our site" pointing at
    nothing, which is worse than refusing the row."""
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/workdays",
        json={"title": "x", "starts_on": date.today().isoformat(), "source": "mirrored"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_anybody_can_look_at_upcoming_workdays(client, db_session):
    org, _ = _org_with_admin(db_session)
    make_workday(db_session, org)

    response = client.get("/workdays")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_a_workday_outside_the_window_is_not_listed(client, db_session):
    org, _ = _org_with_admin(db_session)
    make_workday(
        db_session,
        org,
        starts_on=date.today() + timedelta(days=90),
        ends_on=date.today() + timedelta(days=90),
    )

    assert client.get("/workdays").json() == []
    assert len(client.get("/workdays?days=120").json()) == 1


def test_the_window_is_capped_rather_than_trusted(client, db_session):
    """An unbounded window on a public endpoint is a full table scan anybody
    can ask for."""
    org, _ = _org_with_admin(db_session)
    make_workday(
        db_session,
        org,
        starts_on=date.today() + timedelta(days=900),
        ends_on=date.today() + timedelta(days=900),
    )

    assert client.get("/workdays?days=99999").json() == []


def test_a_signup_is_born_interested_and_nothing_else(client, db_session):
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)

    response = client.post(
        f"/workdays/{project.id}/signups",
        json={"note": "I have a saw certification"},
        headers=auth_headers(volunteer.id),
    )

    assert response.status_code == 201
    assert response.json()["state"] == "interested"
    assert response.json()["reply_message"] is None


def test_signing_up_twice_returns_the_first_one_rather_than_an_error(client, db_session):
    """The outbox retries, and a second tap should not read as an error to
    somebody who did nothing wrong."""
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    headers = auth_headers(volunteer.id)

    first = client.post(f"/workdays/{project.id}/signups", json={}, headers=headers)
    second = client.post(f"/workdays/{project.id}/signups", json={}, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert db_session.query(WorkProjectSignup).count() == 1


def test_a_signup_link_a_browser_would_execute_is_refused(client, db_session):
    """`signup_url` is rendered straight into an `href` in three places, one
    of them `site/public/embed/v1/ourhike.js` running on the organization's
    OWN page - so a `javascript:` URL stored here is stored XSS on their
    site, published by us. `app/schemas/org.py`'s `safe_external_url` is the
    gate every other org-supplied link already passes through; this one was
    missed.
    """
    org, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/workdays",
        json={
            "title": "Cut back the corridor",
            "starts_on": str(date.today()),
            "source": "mirrored",
            "signup_url": "javascript:alert(document.cookie)",
        },
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_a_signup_contact_a_browser_would_execute_is_refused(client, db_session):
    """The same sink: `client/src/org/components.tsx` falls back to
    `signup_contact` for the href when there is no `signup_url`."""
    org, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/workdays",
        json={
            "title": "Cut back the corridor",
            "starts_on": str(date.today()),
            "signup_mode": "contact",
            "signup_contact": "javascript:alert(1)",
        },
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_an_email_address_is_still_a_usable_signup_contact(client, db_session):
    """The guard on `signup_contact` must not refuse the thing it is for: a
    contact is an address or a number as well as a page, which is the same
    set `client/src/lib/safeLink.ts` calls a contact link."""
    org, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/workdays",
        json={
            "title": "Cut back the corridor",
            "starts_on": str(date.today()),
            "signup_mode": "contact",
            "signup_contact": "trails@ramapotrails.org",
        },
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 201


def test_a_mirrored_workday_sends_the_volunteer_to_the_organizations_own_form(client, db_session):
    org, _ = _org_with_admin(db_session)
    project = make_workday(
        db_session,
        org,
        source=ProjectSource.mirrored,
        signup_url="https://ramapotrails.org/volunteer",
    )
    volunteer = make_profile(db_session)

    response = client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id))

    assert response.status_code == 409
    assert "https://ramapotrails.org/volunteer" in response.json()["detail"]


def test_a_contact_mode_workday_does_the_same(client, db_session):
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org, signup_mode=SignupMode.contact, signup_contact="trails@ramapotrails.org")
    volunteer = make_profile(db_session)

    response = client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id))

    assert response.status_code == 409
    assert "trails@ramapotrails.org" in response.json()["detail"]


def test_nobody_can_sign_up_to_a_workday_that_was_called_off(client, db_session):
    org, admin = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    client.post(f"/workdays/{project.id}/cancel", headers=auth_headers(admin.id))
    volunteer = make_profile(db_session)

    response = client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id))

    assert response.status_code == 409


def test_who_signed_up_is_not_readable_by_a_stranger(client, db_session):
    """Names attached to a workday are exactly the class of fact rule 4 keeps
    unpublished."""
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org)

    response = client.get(f"/workdays/{project.id}/signups", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 403


def test_the_organizations_reply_travels_with_the_state(client, db_session):
    """A volunteer reading "waitlisted" and nothing else learns less than one
    reading the organization's own sentence."""
    org, admin = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    signup = client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id)).json()

    replied = client.post(
        f"/workdays/{project.id}/signups/{signup['id']}/reply",
        json={
            "state": "waitlisted",
            "message": "Full for the sawyer crew, short on Tuesday's if that suits you.",
        },
        headers=auth_headers(admin.id),
    )

    assert replied.status_code == 200
    assert replied.json()["state"] == "waitlisted"
    assert "Tuesday" in replied.json()["reply_message"]


def test_an_organization_cannot_reply_interested(client, db_session):
    """It says nothing a volunteer cannot already see, and offering it would
    let an org think it had answered somebody when it had not."""
    org, admin = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    signup = client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id)).json()

    response = client.post(
        f"/workdays/{project.id}/signups/{signup['id']}/reply",
        json={"state": "interested"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_a_volunteer_cannot_confirm_their_own_signup(client, db_session):
    """`confirmed` is set by the organization and by nothing else."""
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    signup = client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id)).json()

    response = client.post(
        f"/workdays/{project.id}/signups/{signup['id']}/reply",
        json={"state": "confirmed"},
        headers=auth_headers(volunteer.id),
    )

    assert response.status_code == 403


def test_pulling_out_is_one_call_and_leaves_no_count_behind(client, db_session):
    """#762's open question, answered the way that issue's instinct pointed.
    Nothing anywhere counts how often somebody has been in this state."""
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id))

    response = client.post(f"/workdays/{project.id}/signups/mine/cancel", headers=auth_headers(volunteer.id))

    assert response.status_code == 200
    assert response.json()["state"] == SignupState.cancelled_by_volunteer.value


def test_a_cancelled_signup_stops_counting_toward_a_cap(client, db_session):
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id))
    client.post(f"/workdays/{project.id}/signups/mine/cancel", headers=auth_headers(volunteer.id))

    listed = client.get("/workdays").json()

    assert listed[0]["interested_count"] == 0


def test_attendance_pre_fills_an_hours_claim_rather_than_creating_one(client, db_session):
    """Hours are claimed, not computed - a number this app wrote is a number no
    organization should report onward to ATC."""
    from app.models.volunteer_hours import VolunteerHoursRecord

    org, admin = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    signup = client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id)).json()

    response = client.post(
        f"/workdays/{project.id}/signups/{signup['id']}/attendance",
        json={"attended": 1},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 200
    assert response.json()["attended"] == 1
    assert db_session.query(VolunteerHoursRecord).count() == 0


def test_a_volunteer_reads_every_hand_they_have_put_up(client, db_session):
    org, _ = _org_with_admin(db_session)
    project = make_workday(db_session, org)
    volunteer = make_profile(db_session)
    client.post(f"/workdays/{project.id}/signups", json={}, headers=auth_headers(volunteer.id))

    mine = client.get("/workdays/signups/mine", headers=auth_headers(volunteer.id)).json()

    assert [row["work_project_id"] for row in mine] == [project.id]
