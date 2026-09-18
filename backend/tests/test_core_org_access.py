"""Tests for who may do what at one organization, and for the invite that
grants it.

`core/org_access.py` is the file every console endpoint's gate goes through,
and the property worth holding is the one ORG_ONBOARDING.md states as a
sentence: *a person can hold several tiers at once, and the UI shows the
union of what they allow - never a role picker.* So these tests build people
who hold two things and check that neither answer suppresses the other.

The second half is #1169's problem 3: an organization can name somebody who
has never opened OurHike, and the grant is applied the first time they sign
in - because **OurHike cannot create a user**, deliberately.
"""

import uuid

from app.core.org_access import resolve_access
from app.core.role_invites import apply_pending_invites, normalise_email
from app.models.club import OrgState
from app.models.org_role import RoleInvite
from app.models.profile import Profile
from tests.factories import (
    make_admin,
    make_assignment,
    make_org,
    make_profile,
    make_role,
)
from tests.tokens import auth_headers


def test_a_pending_admin_is_not_an_admin_yet(client, db_session):
    """`approved_at` is the gate, so an invited secretary who has not answered
    cannot publish a registry."""
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person, approved=False)

    access = resolve_access(db_session, org, person.id)

    assert access.is_admin is False
    assert access.can_touch_registry is False


def test_a_supervisor_is_somebody_a_live_role_reports_to(client, db_session):
    """Derived rather than stored, so a title and a position in the hierarchy
    cannot disagree - there is only one of them."""
    org = make_org(db_session, state=OrgState.claimed)
    lead = make_role(db_session, org, name="Crew lead")
    make_role(db_session, org, name="Maintainer", reports_to_role_id=lead.id)
    person = make_profile(db_session)
    make_assignment(db_session, org, person, role=lead)

    access = resolve_access(db_session, org, person.id)

    assert access.is_supervisor is True
    assert access.can_manage_volunteers is True
    assert access.can_touch_registry is False


def test_a_maintainer_nobody_reports_to_is_not_a_supervisor(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    role = make_role(db_session, org, name="Maintainer")
    person = make_profile(db_session)
    make_assignment(db_session, org, person, role=role)

    access = resolve_access(db_session, org, person.id)

    assert access.is_volunteer is True
    assert access.is_supervisor is False
    assert access.can_read_roster is False


def test_supervising_a_retired_role_is_not_a_permission(client, db_session):
    """A retired role's holders are history, and supervising history is not a
    thing anybody can do."""
    from app.core.time import utc_now

    org = make_org(db_session, state=OrgState.claimed)
    lead = make_role(db_session, org, name="Crew lead")
    make_role(db_session, org, name="Maintainer", reports_to_role_id=lead.id, retired_at=utc_now())
    person = make_profile(db_session)
    make_assignment(db_session, org, person, role=lead)

    assert resolve_access(db_session, org, person.id).is_supervisor is False


def test_a_closed_assignment_is_not_a_live_one(client, db_session):
    import datetime

    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_assignment(db_session, org, person, effective_to=datetime.date.today())

    assert resolve_access(db_session, org, person.id).is_volunteer is False


def test_somebody_who_is_both_an_admin_and_a_maintainer_is_shown_as_both(client, db_session):
    """The union, never a picker. This is the normal case rather than an edge
    one - a trails chair who also looks after three miles."""
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person)
    make_assignment(db_session, org, person)

    access = resolve_access(db_session, org, person.id)

    assert access.is_admin is True
    assert access.is_volunteer is True


def test_a_seat_at_one_organization_grants_nothing_at_another(client, db_session):
    """Somebody who is a trails chair at Ramapo and a maintainer at Hudson
    Highlands is the normal case, and no global enum can say that."""
    ramapo = make_org(db_session, slug="ramapo-trail-conference", state=OrgState.claimed)
    hudson = make_org(db_session, slug="hudson-highlands", name="Hudson Highlands", state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, ramapo, person)

    assert resolve_access(db_session, ramapo, person.id).is_admin is True
    assert resolve_access(db_session, hudson, person.id).is_admin is False


def test_an_address_is_matched_case_insensitively(client, db_session):
    """A roster upload contains both spellings of the same person, and an
    invite that matches only one is an invite that silently never applies."""
    assert normalise_email("  Dana@Ramapotrails.ORG ") == "dana@ramapotrails.org"


def test_an_invite_is_claimed_the_first_time_that_person_signs_in(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    invite = RoleInvite(club_id=org.id, email="dana@ramapotrails.org", full_name="Dana Whitfield")
    db_session.add(invite)
    db_session.commit()
    person = make_profile(db_session)

    applied = apply_pending_invites(db_session, person, "Dana@Ramapotrails.org")

    assert [i.id for i in applied] == [invite.id]
    db_session.refresh(invite)
    assert invite.claimed_by == person.id
    assert invite.claimed_at is not None


def test_a_claimed_invite_is_kept_as_the_audit_row(client, db_session):
    """It is what an organization reads when somebody turns out to hold
    something they should not."""
    org = make_org(db_session, state=OrgState.claimed)
    db_session.add(RoleInvite(club_id=org.id, email="dana@ramapotrails.org"))
    db_session.commit()
    person = make_profile(db_session)

    apply_pending_invites(db_session, person, "dana@ramapotrails.org")

    assert db_session.query(RoleInvite).count() == 1


def test_a_token_with_no_email_claim_claims_nothing_and_breaks_nothing(client, db_session):
    """@unvalidated: whether a real Supabase access token carries an `email`
    claim at all. The code is written so that its absence is harmless - the
    person still gets a profile and can still be added by hand."""
    org = make_org(db_session, state=OrgState.claimed)
    db_session.add(RoleInvite(club_id=org.id, email="dana@ramapotrails.org"))
    db_session.commit()
    person = make_profile(db_session)

    assert apply_pending_invites(db_session, person, None) == []


def test_signing_in_with_an_invited_address_claims_it_through_the_real_request_path(client, db_session):
    """Not the helper - the actual seam every authenticated request crosses,
    because that is where it has to run and where it would be easiest to
    wire up wrongly."""
    org = make_org(db_session, state=OrgState.claimed)
    db_session.add(RoleInvite(club_id=org.id, email="dana@ramapotrails.org"))
    db_session.commit()
    brand_new = str(uuid.uuid4())

    client.get("/profiles/me", headers=auth_headers(brand_new, email="dana@ramapotrails.org"))

    invite = db_session.query(RoleInvite).one()
    assert invite.claimed_by == brand_new


def test_a_returning_caller_does_not_re_run_the_invite_lookup(client, db_session):
    """It runs on the branch that creates the row, not on every request - the
    seam it sits on is crossed by every authenticated call in the app."""
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    db_session.add(RoleInvite(club_id=org.id, email="dana@ramapotrails.org"))
    db_session.commit()

    client.get("/profiles/me", headers=auth_headers(person.id, email="dana@ramapotrails.org"))

    invite = db_session.query(RoleInvite).one()
    assert invite.claimed_at is None
    assert db_session.query(Profile).filter(Profile.id == person.id).count() == 1
