"""Tests for roles, the roster and the sync that loads it.

Three of these are the guardrails that made writing this over HTTP defensible
at all, and they are the ones to read first:

- **A bad sync cannot empty a roster.** `test_a_sync_that_would_release_most_of_the_roster_holds_instead`
  is the 4am case: a changed API field must not release three hundred roles
  and blank the coverage report before anyone wakes up.
- **Supervisors propose, admins confirm.** RLS says who may write, never
  whether a write was right.
- **A volunteer can step back themselves**, without asking anybody.
"""

import uuid
from datetime import date

from app.models.club import OrgState
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_role import OrgRole, RoleInvite, RosterSyncRun
from tests.factories import (
    make_admin,
    make_assignment,
    make_org,
    make_profile,
    make_role,
    make_section,
)
from tests.tokens import auth_headers


def _org_with_admin(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    return org, admin


def _supervisor(db_session, org):
    """Somebody another live role reports to - which is what a supervisor is.

    Derived rather than stored, so making one in a test means making the
    reporting line rather than setting a flag. That is the point: a title and
    a position in the hierarchy cannot disagree if only one of them exists.
    """
    lead_role = make_role(db_session, org, name="Crew lead")
    make_role(db_session, org, name="Maintainer", reports_to_role_id=lead_role.id)
    person = make_profile(db_session)
    make_assignment(db_session, org, person, role=lead_role)
    return person


def test_a_role_is_created_by_an_admin_and_read_by_a_supervisor(client, db_session):
    org, admin = _org_with_admin(db_session)

    created = client.post(
        "/clubs/ramapo-trail-conference/roles",
        json={"name": "Corridor monitor", "category": "stewards", "required": True, "required_by": "ATC"},
        headers=auth_headers(admin.id),
    )

    assert created.status_code == 201
    assert created.json()["required_by"] == "ATC"


def test_a_role_cannot_report_to_itself(client, db_session):
    org, admin = _org_with_admin(db_session)
    role = make_role(db_session, org)

    response = client.patch(
        f"/clubs/ramapo-trail-conference/roles/{role.id}",
        json={"reports_to_role_id": role.id},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_a_role_nobody_ever_held_is_deleted_outright(client, db_session):
    org, admin = _org_with_admin(db_session)
    role = make_role(db_session, org)

    client.delete(f"/clubs/ramapo-trail-conference/roles/{role.id}", headers=auth_headers(admin.id))

    assert db_session.query(OrgRole).count() == 0


def test_a_role_somebody_has_held_is_retired_rather_than_deleted(client, db_session):
    """Deleting it would destroy the answer to "who covered this in June",
    which is the question the whole assignment model is versioned to keep."""
    org, admin = _org_with_admin(db_session)
    role = make_role(db_session, org)
    make_assignment(db_session, org, make_profile(db_session), role=role)

    client.delete(f"/clubs/ramapo-trail-conference/roles/{role.id}", headers=auth_headers(admin.id))

    db_session.expire_all()
    kept = db_session.query(OrgRole).one()
    assert kept.retired_at is not None


def test_a_retired_role_is_out_of_the_default_list_and_available_on_request(client, db_session):
    org, admin = _org_with_admin(db_session)
    role = make_role(db_session, org)
    make_assignment(db_session, org, make_profile(db_session), role=role)
    client.delete(f"/clubs/ramapo-trail-conference/roles/{role.id}", headers=auth_headers(admin.id))
    headers = auth_headers(admin.id)

    assert client.get("/clubs/ramapo-trail-conference/roles", headers=headers).json() == []
    assert len(client.get("/clubs/ramapo-trail-conference/roles?include_retired=true", headers=headers).json()) == 1


def test_a_supervisors_assignment_waits_for_an_admin(client, db_session):
    org, _ = _org_with_admin(db_session)
    # A stretch has to sit inside one of the org's own sections (#1635);
    # the factory's section is miles 11.0 to 14.3.
    make_section(db_session, org)
    supervisor = _supervisor(db_session, org)
    volunteer = make_profile(db_session)

    created = client.post(
        "/clubs/ramapo-trail-conference/assignments",
        json={"person_id": volunteer.id, "start_mile": 11.0, "end_mile": 14.3},
        headers=auth_headers(supervisor.id),
    )

    assert created.status_code == 201
    assert created.json()["proposed_by"] == supervisor.id
    assert created.json()["confirmed_at"] is None


def test_an_admins_own_assignment_is_live_immediately(client, db_session):
    org, admin = _org_with_admin(db_session)
    # A stretch has to sit inside one of the org's own sections (#1635);
    # the factory's section is miles 11.0 to 14.3.
    make_section(db_session, org)
    volunteer = make_profile(db_session)

    created = client.post(
        "/clubs/ramapo-trail-conference/assignments",
        json={"person_id": volunteer.id, "start_mile": 11.0, "end_mile": 14.3},
        headers=auth_headers(admin.id),
    )

    assert created.json()["proposed_by"] is None
    assert created.json()["confirmed_at"] is not None


def test_an_admin_confirms_a_supervisors_proposal(client, db_session):
    org, admin = _org_with_admin(db_session)
    # A stretch has to sit inside one of the org's own sections (#1635);
    # the factory's section is miles 11.0 to 14.3.
    make_section(db_session, org)
    supervisor = _supervisor(db_session, org)
    volunteer = make_profile(db_session)
    proposal = client.post(
        "/clubs/ramapo-trail-conference/assignments",
        json={"person_id": volunteer.id, "start_mile": 11.0, "end_mile": 12.0},
        headers=auth_headers(supervisor.id),
    ).json()

    confirmed = client.post(
        f"/clubs/ramapo-trail-conference/assignments/{proposal['id']}/confirm",
        headers=auth_headers(admin.id),
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["confirmed_by"] == admin.id


def test_a_volunteer_can_step_back_from_their_own_section_without_asking(client, db_session):
    """The organization's feed can already deactivate them; they should have at
    least that much say."""
    org, _ = _org_with_admin(db_session)
    volunteer = make_profile(db_session)
    assignment = make_assignment(db_session, org, volunteer)

    response = client.post(
        f"/clubs/ramapo-trail-conference/assignments/{assignment.id}/step-back",
        headers=auth_headers(volunteer.id),
    )

    assert response.status_code == 200
    db_session.refresh(assignment)
    assert assignment.effective_to == date.today()


def test_stepping_back_closes_the_row_rather_than_deleting_it(client, db_session):
    org, _ = _org_with_admin(db_session)
    volunteer = make_profile(db_session)
    assignment = make_assignment(db_session, org, volunteer)

    client.post(
        f"/clubs/ramapo-trail-conference/assignments/{assignment.id}/step-back",
        headers=auth_headers(volunteer.id),
    )

    assert db_session.query(MaintainerAssignment).count() == 1


def test_nobody_can_step_somebody_else_back(client, db_session):
    org, _ = _org_with_admin(db_session)
    assignment = make_assignment(db_session, org, make_profile(db_session))

    response = client.post(
        f"/clubs/ramapo-trail-conference/assignments/{assignment.id}/step-back",
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 403


def test_the_roster_shows_people_who_have_never_opened_ourhike(client, db_session):
    """An organization's roster is its roster whether or not its people have
    discovered this app - a list showing only the signed-in half would look
    like the org had lost most of its volunteers."""
    org, admin = _org_with_admin(db_session)
    make_assignment(db_session, org, make_profile(db_session, display_name="Ana"))
    client.post(
        "/clubs/ramapo-trail-conference/invites",
        json={"email": "Dana@Ramapotrails.org", "full_name": "Dana Whitfield"},
        headers=auth_headers(admin.id),
    )

    roster = client.get("/clubs/ramapo-trail-conference/roster", headers=auth_headers(admin.id)).json()

    pending = [row for row in roster if row["pending_invite"]]
    assert [row["email"] for row in pending] == ["dana@ramapotrails.org"]
    assert any(row["display_name"] == "Ana" for row in roster)


def test_the_roster_is_not_readable_by_a_signed_in_stranger(client, db_session):
    """Rule 4: nothing about a named volunteer is ever published."""
    make_org(db_session, state=OrgState.claimed)

    response = client.get("/clubs/ramapo-trail-conference/roster", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 403


def test_inviting_the_same_person_twice_does_not_make_a_second_invite(client, db_session):
    """A roster re-uploaded weekly contains every name every time."""
    org, admin = _org_with_admin(db_session)
    headers = auth_headers(admin.id)
    body = {"email": "dana@ramapotrails.org"}

    client.post("/clubs/ramapo-trail-conference/invites", json=body, headers=headers)
    client.post("/clubs/ramapo-trail-conference/invites", json=body, headers=headers)

    assert db_session.query(RoleInvite).count() == 1


def test_a_sync_adds_people_it_has_never_seen(client, db_session):
    org, admin = _org_with_admin(db_session)

    result = client.post(
        "/clubs/ramapo-trail-conference/roster/sync",
        json={
            "source": "uploaded roster.csv",
            "entries": [
                {"email": "ana@ramapotrails.org", "full_name": "Ana Reyes"},
                {"email": "dev@ramapotrails.org", "full_name": "Dev Patel"},
            ],
        },
        headers=auth_headers(admin.id),
    ).json()

    assert result["added"] == 2
    assert db_session.query(RoleInvite).count() == 2


def test_every_sync_run_writes_an_audit_row(client, db_session):
    """The audit row is what made writing the roster over HTTP defensible."""
    org, admin = _org_with_admin(db_session)

    client.post(
        "/clubs/ramapo-trail-conference/roster/sync",
        json={"source": "nightly pull", "entries": [{"email": "ana@ramapotrails.org"}]},
        headers=auth_headers(admin.id),
    )

    run = db_session.query(RosterSyncRun).one()
    assert run.source == "nightly pull"
    assert run.run_by == admin.id


def test_a_sync_that_would_release_most_of_the_roster_holds_instead(client, db_session):
    """The 4am case. A changed API field must not release three hundred roles
    and blank the coverage report before anybody wakes up."""
    org, admin = _org_with_admin(db_session)
    for _ in range(5):
        make_assignment(db_session, org, make_profile(db_session))

    result = client.post(
        "/clubs/ramapo-trail-conference/roster/sync",
        json={"source": "their API, 4am", "entries": []},
        headers=auth_headers(admin.id),
    ).json()

    assert result["deactivated"] == 0
    assert result["deactivations_held"] == 5
    assert len(result["held_person_ids"]) == 5
    assert "check the list and confirm it yourself" in result["held_reason"]


def test_a_held_sync_still_applies_everything_it_added(client, db_session):
    """Holding the deactivations must not hold the additions - a roster that
    stops growing is as broken as one that empties."""
    org, admin = _org_with_admin(db_session)
    for _ in range(5):
        make_assignment(db_session, org, make_profile(db_session))

    result = client.post(
        "/clubs/ramapo-trail-conference/roster/sync",
        json={"source": "their API", "entries": [{"email": "new@ramapotrails.org"}]},
        headers=auth_headers(admin.id),
    ).json()

    assert result["added"] == 1
    assert result["deactivations_held"] == 5
    assert db_session.query(RoleInvite).count() == 1


def test_a_small_deactivation_goes_through(client, db_session):
    """One person off a roster of twenty is a Tuesday, not a catastrophe."""
    org, admin = _org_with_admin(db_session)
    staying = [make_profile(db_session) for _ in range(20)]
    for person in staying:
        make_assignment(db_session, org, person)
    for person in staying:
        invite = RoleInvite(
            club_id=org.id,
            email=f"{person.id}@ramapotrails.org",
            claimed_at=date.today(),
            claimed_by=person.id,
        )
        db_session.add(invite)
    db_session.commit()

    result = client.post(
        "/clubs/ramapo-trail-conference/roster/sync",
        json={
            "source": "their API",
            "entries": [{"email": f"{person.id}@ramapotrails.org"} for person in staying[:-1]],
        },
        headers=auth_headers(admin.id),
    ).json()

    assert result["deactivations_held"] == 0
    assert result["deactivated"] == 1


def test_a_section_assignment_is_visible_on_the_roster(client, db_session):
    org, admin = _org_with_admin(db_session)
    section = make_section(db_session, org, name="Pine Meadow North")
    role = make_role(db_session, org, name="Maintainer")
    make_assignment(db_session, org, make_profile(db_session), role=role, section=section)

    roster = client.get("/clubs/ramapo-trail-conference/roster", headers=auth_headers(admin.id)).json()

    assert roster[0]["roles"] == ["Maintainer"]
    assert roster[0]["sections"] == ["Pine Meadow North"]


def test_assigning_somebody_who_has_never_signed_in_says_what_to_do_instead(client, db_session):
    """#1169's problem 3 arriving at a screen: OurHike cannot create a user, so
    an admin typing a name gets the route that works rather than a 500."""
    org, admin = _org_with_admin(db_session)
    # A stretch has to sit inside one of the org's own sections (#1635);
    # the factory's section is miles 11.0 to 14.3.
    make_section(db_session, org)

    response = client.post(
        "/clubs/ramapo-trail-conference/assignments",
        json={"person_id": str(uuid.uuid4()), "start_mile": 11.0, "end_mile": 12.0},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422
    assert "Invite them by email instead" in response.json()["detail"]
