"""Tests for `/clubs` - registering an organization and running one (#1539).

What these hold, in the order the design cares about them:

- **Registering names you as the first admin**, so there is no anonymous
  path and the domain check runs against a *verified* address rather than a
  typed one.
- **A decline is reversible and is never a rejection.** The pair of tests at
  the bottom is the whole of that promise: declining pauses, approving after
  declining clears the refusal.
- **A contested claim freezes and waits for a person.** No automatic exit,
  because a timer resolves the contest in favour of whoever was patient.
- **Deleting an organization does not delete its volunteers' records**, which
  belong to them and survive the org winding up.
"""

import uuid

from app.models.club import Club, OrgAdmin, OrgState
from app.models.org_role import RoleInvite
from app.models.volunteer_hours import HoursActivity, VolunteerHoursRecord
from tests.factories import make_admin, make_org, make_profile
from tests.tokens import auth_headers

_REGISTRATION = {
    "name": "Ramapo Trail Conference",
    "slug": "ramapo-trail-conference",
    "domain": "ramapotrails.org",
    "website": "https://ramapotrails.org",
    "membership_url": "https://ramapotrails.org/join",
    "donation_url": "https://ramapotrails.org/give",
    "admins": [{"email": "joseph@ramapotrails.org", "title": "Crew lead"}],
}


def _register(client, user_id, *, email="maria@ramapotrails.org", **overrides):
    return client.post(
        "/clubs",
        json={**_REGISTRATION, **overrides},
        headers=auth_headers(user_id, email=email),
    )


def test_registering_requires_an_account(client):
    assert client.post("/clubs", json=_REGISTRATION).status_code == 401


def test_registering_makes_the_caller_an_approved_admin(client, db_session):
    user_id = str(uuid.uuid4())

    response = _register(client, user_id)

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "ramapo-trail-conference"
    assert body["state"] == "claimed"
    seats = db_session.query(OrgAdmin).all()
    assert [seat.person_id for seat in seats] == [user_id]
    assert seats[0].approved_at is not None


def test_the_other_admins_become_invites_rather_than_seats(client, db_session):
    """OurHike cannot create a user, so a named admin who has never signed in
    is a pending grant rather than a row claiming they agreed to anything."""
    _register(client, str(uuid.uuid4()))

    invites = db_session.query(RoleInvite).all()
    assert [invite.email for invite in invites] == ["joseph@ramapotrails.org"]
    assert invites[0].claimed_at is None


def test_nobody_can_register_an_organization_they_have_no_address_at(client):
    response = _register(
        client,
        str(uuid.uuid4()),
        email="somebody@gmail.com",
        admins=[{"email": "friend@gmail.com"}],
    )

    assert response.status_code == 422
    assert "ramapotrails.org" in response.json()["detail"]


def test_an_invited_admin_on_the_domain_satisfies_the_check(client):
    """The caller does not personally have to hold the address - one of the
    three does, which is what an org whose chair uses a personal email needs."""
    response = _register(
        client,
        str(uuid.uuid4()),
        email="chair@gmail.com",
        admins=[{"email": "secretary@ramapotrails.org"}],
    )

    assert response.status_code == 201


def test_a_subdomain_counts_as_the_organizations_domain(client):
    response = _register(client, str(uuid.uuid4()), email="maria@trails.ramapotrails.org")

    assert response.status_code == 201


def test_a_taken_address_is_refused_by_name(client):
    _register(client, str(uuid.uuid4()))

    response = _register(client, str(uuid.uuid4()))

    assert response.status_code == 409
    assert "/org/ramapo-trail-conference" in response.json()["detail"]


def test_a_reserved_slug_is_refused(client):
    response = _register(client, str(uuid.uuid4()), slug="volunteers")

    assert response.status_code == 422


def test_a_slug_with_spaces_is_refused(client):
    response = _register(client, str(uuid.uuid4()), slug="Ramapo Trail Conference")

    assert response.status_code == 422


def test_anybody_can_read_a_published_organization(client, db_session):
    make_org(db_session)

    response = client.get("/clubs/ramapo-trail-conference")

    assert response.status_code == 200
    assert response.json()["name"] == "Ramapo Trail Conference"


def test_a_deleted_organization_answers_404_rather_than_410(client, db_session):
    """A person who should not know an org ever existed learns nothing from a
    404, and the people entitled to know already have its export."""
    make_org(db_session, state=OrgState.deleted)

    assert client.get("/clubs/ramapo-trail-conference").status_code == 404


def test_the_sidebar_reads_its_own_permissions_from_the_server(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)

    response = client.get("/clubs/ramapo-trail-conference/access", headers=auth_headers(admin.id))

    assert response.status_code == 200
    assert response.json()["is_admin"] is True
    assert response.json()["can_touch_registry"] is True


def test_a_signed_in_stranger_gets_every_flag_false_rather_than_a_403(client, db_session):
    """The public org page and the claim flow both need this to resolve rather
    than refuse - and the console's sidebar reads it to draw nothing."""
    make_org(db_session, state=OrgState.claimed)

    response = client.get("/clubs/ramapo-trail-conference/access", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 200
    assert response.json()["is_admin"] is False
    assert response.json()["can_manage_volunteers"] is False


def test_claiming_needs_an_address_at_the_organizations_domain(client, db_session):
    make_org(db_session)
    claimer = make_profile(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={"title": "Trails chair"},
        headers=auth_headers(claimer.id, email="someone@gmail.com"),
    )

    assert response.status_code == 403


def test_claiming_an_unclaimed_organization_makes_you_its_first_codeowner(client, db_session):
    make_org(db_session)
    claimer = make_profile(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={"title": "Trails chair"},
        headers=auth_headers(claimer.id, email="maria@ramapotrails.org"),
    )

    assert response.status_code == 200
    assert response.json()["state"] == "claimed"
    seat = db_session.query(OrgAdmin).one()
    assert seat.person_id == claimer.id
    assert seat.is_codeowner is True


def test_a_second_claim_freezes_the_organization_for_a_person(client, db_session):
    """Two people at one domain claiming one org is not a race to be won."""
    make_org(db_session)
    first = make_profile(db_session)
    second = make_profile(db_session)
    client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={},
        headers=auth_headers(first.id, email="maria@ramapotrails.org"),
    )

    response = client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={},
        headers=auth_headers(second.id, email="joseph@ramapotrails.org"),
    )

    assert response.status_code == 409
    assert db_session.query(Club).one().state == OrgState.frozen


def test_a_frozen_organization_has_no_automatic_way_out(client, db_session):
    make_org(db_session, state=OrgState.frozen)
    claimer = make_profile(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={},
        headers=auth_headers(claimer.id, email="maria@ramapotrails.org"),
    )

    assert response.status_code == 409
    assert db_session.query(Club).one().state == OrgState.frozen


def test_only_the_person_invited_can_answer_their_own_invitation(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    invited = make_profile(db_session)
    seat = make_admin(db_session, org, invited, approved=False)

    response = client.post(
        f"/clubs/ramapo-trail-conference/admins/{seat.id}/approve",
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 403


def test_declining_pauses_and_is_never_a_rejection(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    invited = make_profile(db_session)
    seat = make_admin(db_session, org, invited, approved=False)

    declined = client.post(
        f"/clubs/ramapo-trail-conference/admins/{seat.id}/decline",
        json={"reason": "I do not know what this is - ask Joseph"},
        headers=auth_headers(invited.id),
    )

    assert declined.status_code == 200
    db_session.refresh(seat)
    assert seat.declined_at is not None
    assert seat.approved_at is None


def test_approving_after_declining_clears_the_refusal(client, db_session):
    """The recoverable case must not look final: the common cause of a decline
    is somebody who did not know what OurHike was when they were asked."""
    org = make_org(db_session, state=OrgState.claimed)
    invited = make_profile(db_session)
    seat = make_admin(db_session, org, invited, approved=False)
    client.post(
        f"/clubs/ramapo-trail-conference/admins/{seat.id}/decline",
        json={"reason": "not now"},
        headers=auth_headers(invited.id),
    )

    response = client.post(
        f"/clubs/ramapo-trail-conference/admins/{seat.id}/approve",
        headers=auth_headers(invited.id),
    )

    assert response.status_code == 200
    db_session.refresh(seat)
    assert seat.approved_at is not None
    assert seat.declined_at is None
    assert seat.decline_reason is None


def test_the_address_in_every_route_cannot_be_edited_away(client, db_session):
    """`slug` has no field on the update model, so sending one changes nothing
    rather than breaking every embed an organization has already pasted."""
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)

    response = client.patch(
        "/clubs/ramapo-trail-conference",
        json={"name": "Ramapo Trails", "slug": "something-else"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Ramapo Trails"
    assert response.json()["slug"] == "ramapo-trail-conference"


def test_a_volunteers_hours_survive_the_organization_deleting_itself(client, db_session):
    """They belong to the person, not the organization. An org winding up is
    not an event that erases somebody else's logbook."""
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    volunteer = make_profile(db_session)
    hours = VolunteerHoursRecord(
        user_id=volunteer.id,
        club_id=org.id,
        worked_on="2026-08-18",
        hours=5.5,
        activity=HoursActivity.maintenance,
    )
    db_session.add(hours)
    db_session.commit()

    response = client.delete("/clubs/ramapo-trail-conference", headers=auth_headers(admin.id))

    assert response.status_code == 204
    assert db_session.query(VolunteerHoursRecord).count() == 1


def test_an_organization_can_take_everything_it_has_here(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)

    response = client.get("/clubs/ramapo-trail-conference/export", headers=auth_headers(admin.id))

    assert response.status_code == 200
    body = response.json()
    assert body["org"]["slug"] == "ramapo-trail-conference"
    assert set(body) >= {"org", "parks", "trails", "sections", "roles", "workdays", "admins"}


def test_the_export_is_not_a_public_read(client, db_session):
    make_org(db_session, state=OrgState.claimed)

    response = client.get("/clubs/ramapo-trail-conference/export", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 403


def test_a_nomination_creates_an_unclaimed_org_for_a_person_to_read(client, db_session):
    hiker = make_profile(db_session)

    response = client.post(
        "/clubs/nominations",
        json={"name": "Hudson Highlands Land Trust", "website": "https://hhlt.org"},
        headers=auth_headers(hiker.id),
    )

    assert response.status_code == 202
    nominated = db_session.query(Club).filter(Club.name == "Hudson Highlands Land Trust").one()
    assert nominated.state == OrgState.unclaimed


def test_an_unclaimed_organization_still_appears_in_the_list(client, db_session):
    """It is exactly what the claim flow has to be able to find, and its trails
    are already on phones."""
    make_org(db_session)

    slugs = [org["slug"] for org in client.get("/clubs").json()]

    assert "ramapo-trail-conference" in slugs
