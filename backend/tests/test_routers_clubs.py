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

from app.core.time import utc_now
from app.models.club import Club, OrgAdmin, OrgState, VerifiedBy
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


def test_an_invited_admin_on_the_domain_gets_the_registration_accepted(client):
    """The caller does not personally have to hold the address - one of the
    three does, which is what an org whose chair uses a personal email needs.

    Accepted, but see the test below for what it is accepted AS. The address
    here is one the registrant typed, and typing it proves nothing.
    """
    response = _register(
        client,
        str(uuid.uuid4()),
        email="chair@gmail.com",
        admins=[{"email": "secretary@ramapotrails.org"}],
    )

    assert response.status_code == 201


def test_a_registration_proved_only_by_a_typed_address_is_held(client, db_session):
    """An address the registrant typed for somebody else is a CLAIM about
    that person, not evidence about the registrant.

    Taking it as evidence let anybody register any organization under any
    domain - type one address at it, and the real org is locked out of its
    own slug with a stranger recorded as its first admin. So the row is
    written and the registration is accepted, but nothing about it is called
    verified: `pending`, and `verified_by` stays null because nobody has
    verified anything yet. `approve_seat` is where that changes.
    """
    response = _register(
        client,
        str(uuid.uuid4()),
        email="chair@gmail.com",
        admins=[{"email": "secretary@ramapotrails.org"}],
    )

    assert response.status_code == 201
    assert response.json()["state"] == "pending"
    club = db_session.query(Club).one()
    assert club.state == OrgState.pending
    assert club.verified_by is None


def test_a_registration_the_registrant_can_prove_is_claimed_outright(client, db_session):
    """The other side of the same fork, pinned so the two cannot drift: when
    the signed-in account itself holds the domain, the provider has already
    verified that address, and there is nothing left to wait for."""
    _register(client, str(uuid.uuid4()), email="maria@ramapotrails.org")

    club = db_session.query(Club).one()
    assert club.state == OrgState.claimed
    assert club.verified_by == VerifiedBy.email


def test_a_held_organization_is_not_in_the_public_list(client, db_session):
    """`unclaimed` is public because it is a real organization whose trails
    hikers already walk. A held registration is not that - nobody at the
    organization has confirmed it exists here, so publishing it would put
    our word behind a row a stranger typed."""
    _register(
        client,
        str(uuid.uuid4()),
        email="chair@gmail.com",
        admins=[{"email": "secretary@ramapotrails.org"}],
    )

    listed = client.get("/clubs").json()

    assert [org["slug"] for org in listed] == []


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


def test_an_invited_admin_gets_a_seat_the_first_time_they_sign_in(client, db_session):
    """The registration's other admins become `RoleInvite` rows, because
    OurHike cannot create a user (#1169's problem 3). Nothing turned one into
    a seat, so an organization registered through the product had exactly one
    admin forever - and `is_codeowner`'s three-approvals rule, which every
    registry change needs, could never be satisfied by anybody.

    The seat arrives un-approved: being invited is not agreeing, and
    `approve_seat` is where the person says yes.
    """
    _register(client, str(uuid.uuid4()))
    invitee = str(uuid.uuid4())

    # No profile row for them yet - this request is their first sign-in, and
    # `/access` is what the console calls when somebody opens an org.
    client.get(
        "/clubs/ramapo-trail-conference/access",
        headers=auth_headers(invitee, email="joseph@ramapotrails.org"),
    )

    seat = db_session.query(OrgAdmin).filter(OrgAdmin.person_id == invitee).one_or_none()
    assert seat is not None
    assert seat.approved_at is None


def test_an_invite_reaches_somebody_who_already_had_an_account(client, db_session):
    """Invites were applied only on the branch that CREATED a profile row, so
    an invite written after that person's first sign-in never applied at all
    - which is every invite to somebody who already uses OurHike, and the
    common case for an organization naming colleagues who are already hikers.
    """
    _register(client, str(uuid.uuid4()))
    # They already have a profile: they are a hiker who signed in last year.
    invitee = make_profile(db_session)

    client.get(
        "/clubs/ramapo-trail-conference/access",
        headers=auth_headers(invitee.id, email="joseph@ramapotrails.org"),
    )

    seat = db_session.query(OrgAdmin).filter(OrgAdmin.person_id == invitee.id).one_or_none()
    assert seat is not None


def test_a_held_organization_is_released_by_somebody_who_holds_its_domain(client, db_session):
    """What `pending` is waiting for, and the only thing that ends it.

    Approving is the act that carries the meaning, rather than merely signing
    in: signing in proves somebody controls the address, and approving proves
    they agree this organization's registration is theirs. An org verified by
    a sign-in alone would be verified by a secretary who opened OurHike to
    look at a trail.
    """
    _register(
        client,
        str(uuid.uuid4()),
        email="chair@gmail.com",
        admins=[{"email": "secretary@ramapotrails.org"}],
    )
    secretary = make_profile(db_session)
    headers = auth_headers(secretary.id, email="secretary@ramapotrails.org")
    client.get("/clubs/ramapo-trail-conference/access", headers=headers)
    seat = db_session.query(OrgAdmin).filter(OrgAdmin.person_id == secretary.id).one()

    response = client.post(f"/clubs/ramapo-trail-conference/admins/{seat.id}/approve", headers=headers)

    assert response.status_code == 200
    db_session.expire_all()
    club = db_session.query(Club).one()
    assert club.state == OrgState.claimed
    assert club.verified_by == VerifiedBy.email


def test_a_held_organization_stays_held_when_the_approver_is_not_on_its_domain(client, db_session):
    """The registrant approving their own invitation to their own squat is
    the attack this state exists to stop, so approving from off the domain
    releases nothing - the seat is theirs, the verification is not."""
    registrant = str(uuid.uuid4())
    _register(
        client,
        registrant,
        email="chair@gmail.com",
        admins=[{"email": "secretary@ramapotrails.org"}],
    )
    seat = db_session.query(OrgAdmin).filter(OrgAdmin.person_id == registrant).one()

    client.post(
        f"/clubs/ramapo-trail-conference/admins/{seat.id}/approve",
        headers=auth_headers(registrant, email="chair@gmail.com"),
    )

    db_session.expire_all()
    club = db_session.query(Club).one()
    assert club.state == OrgState.pending
    assert club.verified_by is None


def test_the_real_organization_can_still_claim_a_held_registration(client, db_session):
    """The recourse, and the reason holding is enough rather than refusing.

    A stranger registering somebody else's organization does not lock them
    out of it: `pending` is not `claimed`, so the ordinary claim flow is open
    to anybody who holds an address at the domain, and taking it makes them a
    codeowner of the org that was sitting in their name.
    """
    _register(
        client,
        str(uuid.uuid4()),
        email="squatter@gmail.com",
        admins=[{"email": "secretary@ramapotrails.org"}],
    )
    maria = make_profile(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={},
        headers=auth_headers(maria.id, email="maria@ramapotrails.org"),
    )

    assert response.status_code == 200
    db_session.expire_all()
    club = db_session.query(Club).one()
    assert club.state == OrgState.claimed
    seat = db_session.query(OrgAdmin).filter(OrgAdmin.person_id == maria.id).one()
    assert seat.is_codeowner is True


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
    # The admin invitation the seat came from: accepting a seat needs one
    # behind it (#1635), and an invited person is who this test is about.
    db_session.add(
        RoleInvite(
            club_id=org.id,
            email="invited@ramapotrails.org",
            grants_admin_seat=True,
            claimed_by=invited.id,
            claimed_at=utc_now(),
        )
    )
    db_session.commit()
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
