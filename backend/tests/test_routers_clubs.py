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

import pytest

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


def test_a_claim_from_off_the_domain_leaves_a_claimed_organization_alone(client, db_session):
    """The freeze is for two people at one domain, not for whoever asks.

    `frozen` has no automatic exit, by design - a timer would resolve a
    contested claim in favour of whoever was patient. That makes the freeze
    an irreversible act, so nothing may reach it before the caller's address
    has been checked against the org's domain. One signed-in account walking
    the public list would otherwise take every organization on it offline.
    """
    make_org(db_session, state=OrgState.claimed)
    stranger = make_profile(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={},
        headers=auth_headers(stranger.id, email="somebody@gmail.com"),
    )

    assert response.status_code == 403
    assert db_session.query(Club).one().state == OrgState.claimed


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


# NOMINATING AN ORG IS TESTED WHERE IT LIVES NOW,
# tests/test_routers_nominations.py. This asserted that `POST /clubs/nominations`
# created an unclaimed org a maintainer could read; it now also reads the
# club's own pages, lets the hiker review what was found, stores only what the
# hiker kept, and refuses outright for a club that has said never again -
# none of which this file is the home for.


def test_an_unclaimed_organization_still_appears_in_the_list(client, db_session):
    """It is exactly what the claim flow has to be able to find, and its trails
    are already on phones."""
    make_org(db_session)

    slugs = [org["slug"] for org in client.get("/clubs").json()]

    assert "ramapo-trail-conference" in slugs


# --------------------------------------------------------------------- #
# The links an organization gives us are rendered as hrefs on THEIR site,
# in the console, and on every one of their sections in the hiker's app.
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "hostile",
    [
        "javascript:alert(document.cookie)",
        "JavaScript:alert(1)",
        "  javascript:alert(1)  ",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "jar:http://x!/",
        "//evil.example/looks-relative",
    ],
)
def test_a_donation_link_a_browser_would_execute_is_refused_at_registration(client, db_session, hostile):
    """The card that renders this is in a hiker's hand, on a trail.

    An allow-list, so a scheme nobody here has heard of is refused rather
    than waited for.
    """
    registrar = make_profile(db_session)

    response = client.post(
        "/clubs",
        json={
            "name": "Ramapo Trail Conference",
            "slug": "ramapo-trail-conference",
            "domain": "ramapotrails.org",
            "donation_url": hostile,
            "admins": [],
        },
        headers=auth_headers(registrar.id, email="chair@ramapotrails.org"),
    )

    assert response.status_code == 422


def test_the_same_link_is_refused_when_edited_in_afterwards(client, db_session):
    """The links usually arrive after the trails do, so the settings form is
    the one an organization actually uses. A gate only on registration would
    be a gate that only looked like one."""
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person)

    response = client.patch(
        f"/clubs/{org.slug}",
        json={"membership_url": "javascript:alert(1)"},
        headers=auth_headers(person.id),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "fine",
    ["https://ramapotrails.org/join", "http://ramapotrails.org/give", "  https://x.org/a  "],
)
def test_an_ordinary_membership_page_still_goes_through(client, db_session, fine):
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person)

    response = client.patch(f"/clubs/{org.slug}", json={"membership_url": fine}, headers=auth_headers(person.id))

    assert response.status_code == 200
    assert response.json()["membership_url"] == fine.strip()


def test_an_organization_with_no_donation_page_has_no_donation_link(client, db_session):
    """Absent is a real answer. A blank field must not become a dead link."""
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person)

    response = client.patch(f"/clubs/{org.slug}", json={"donation_url": "   "}, headers=auth_headers(person.id))

    assert response.status_code == 200
    assert response.json()["donation_url"] is None


def test_the_export_carries_the_roster_the_settings_screen_promises(client, db_session):
    """Everything else in the file is already published.

    An export without the roster would be a file an organization could have
    rebuilt from the map, sitting behind an admin check with nothing left to
    protect - and the settings screen shows a Roster tile beside the button.
    """
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person)

    body = client.get(f"/clubs/{org.slug}/export", headers=auth_headers(person.id)).json()

    assert "roster" in body
    assert isinstance(body["roster"], list)


def test_a_supervisor_can_read_the_roster_screen_and_cannot_download_it(client, db_session):
    """`can_read_roster` is enough for the screen and deliberately not enough
    for the file. A screen is one org's supervisor looking something up; a
    file is a copy of everybody's name and address leaving the building."""
    org = make_org(db_session, state=OrgState.claimed)
    supervisor = make_profile(db_session)

    response = client.get(f"/clubs/{org.slug}/export", headers=auth_headers(supervisor.id))

    assert response.status_code == 403


def test_the_export_does_not_carry_a_volunteers_own_hours(client, db_session):
    """Hours belong to the person, travel with them when the organization is
    deleted, and are theirs to export from their own account."""
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person)

    body = client.get(f"/clubs/{org.slug}/export", headers=auth_headers(person.id)).json()

    assert "hours" not in body
    assert "reports" not in body
