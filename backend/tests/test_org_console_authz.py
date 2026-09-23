"""The five places #1635 found the organization console trusting itself too far.

#1635 - The organization console's new endpoints trust self-registered orgs
with maintainer powers, seats and mail. Each test here was written red against
`main` before the fix it names, and every one of them states what a hiker or
an organization would have lost rather than which line changed.

The shared premise, and why it is not itself a bug: `POST /clubs` makes the
registrant a claimed, approved admin the moment their own verified address is
at the domain they typed. That is the design (ORG_ONBOARDING.md) and it holds
for a real trail club. It also holds for anybody with a free-mail address who
types that free-mail domain - so nothing downstream may treat "an approved
admin of a claimed org" as "somebody a maintainer stands behind".
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.codeowners import codeowners_block
from app.models.club import Club, OrgAdmin, OrgState
from app.models.field_note import FieldNote
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.nomination import NominationContact, NominationRefusal, OrgNomination
from app.models.org_role import RoleInvite
from app.models.profile import Profile
from tests.factories import make_admin, make_assignment, make_org, make_profile, make_role, make_section
from tests.tokens import auth_headers

_POI = "atc_shelters:spring-1"


def _self_registered(client, db_session, *, domain="freemail.example"):
    """An organization anybody could register: their own address, their own domain."""
    person = make_profile(db_session)
    headers = auth_headers(person.id, email=f"me@{domain}")
    response = client.post(
        "/clubs",
        json={"name": "Totally Real Trail Club", "slug": "totally-real", "domain": domain},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["state"] == "claimed"
    club = db_session.query(Club).filter(Club.slug == "totally-real").one()
    return club, person, headers


def _note(db, reporter_id, *, mile, days_ago=1):
    db.add(
        FieldNote(
            id=str(uuid.uuid4()),
            reporter_id=reporter_id,
            poi_id=_POI,
            mile=mile,
            observation="not_found",
            observed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago),
            posted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            reporter_type="thru",
        )
    )
    db.commit()


# --------------------------------------------------------------------------- #
# 1. A console assignment is not a maintainer's word to hikers.
# --------------------------------------------------------------------------- #


def test_a_self_registered_orgs_own_assignment_does_not_let_one_note_mark_a_spring_missing(client, db_session):
    """One note from a covering maintainer puts "reported missing" on a pin.

    That weight was earned by an assignment a maintainer loaded from a
    reviewed file. An organization that registered itself a minute ago and
    drew itself a long section must not be able to buy it.
    """
    club, person, headers = _self_registered(client, db_session)
    section = make_section(db_session, club, name="Everything", start_mile=0.0, end_mile=2200.0)
    created = client.post(
        "/clubs/totally-real/assignments",
        json={"person_id": person.id, "section_id": section.id, "start_mile": 0.0, "end_mile": 2200.0},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    _note(db_session, person.id, mile=500.0)

    assert client.get("/disputes").json() == []


def test_a_self_registered_orgs_own_assignment_does_not_open_other_hikers_thanks(client, db_session):
    club, person, headers = _self_registered(client, db_session)
    section = make_section(db_session, club, name="Everything", start_mile=0.0, end_mile=2200.0)
    client.post(
        "/clubs/totally-real/assignments",
        json={"person_id": person.id, "section_id": section.id, "start_mile": 0.0, "end_mile": 2200.0},
        headers=headers,
    )

    filed = client.post(
        "/reports",
        json={
            "type": "thanks",
            "reporter_type": "thru",
            "lat": 37.9,
            "lon": -79.1,
            "mile": 1043,
            "note": "Thank you for the blowdowns",
        },
        headers=auth_headers(str(uuid.uuid4())),
    )
    assert filed.status_code == 201, filed.text

    # Neither resolved to them when it arrived, nor delivered to them after.
    assert filed.json()["maintainer_id"] is None
    assert filed.json()["club_id"] is None
    assert client.get("/reports/thanks", headers=headers).json() == []


def test_an_unconfirmed_proposal_is_not_a_maintainers_word(client, db_session):
    """Supervisors propose, admins confirm - and until an admin has, the row is a proposal."""
    club = make_org(db_session)
    proposer = make_profile(db_session)
    volunteer = make_profile(db_session)
    make_assignment(db_session, club, volunteer, start_mile=400.0, end_mile=600.0, proposed_by=proposer.id)

    _note(db_session, volunteer.id, mile=500.0)

    assert client.get("/disputes").json() == []


def test_a_file_loaded_assignment_still_carries_a_maintainers_word(client, db_session):
    """The reviewed-file path is the one this fix leaves alone."""
    club = make_org(db_session)
    maintainer = make_profile(db_session)
    make_assignment(db_session, club, maintainer, start_mile=400.0, end_mile=600.0)

    _note(db_session, maintainer.id, mile=500.0)

    [row] = client.get("/disputes").json()
    assert row["maintainer_said"] is True


def test_an_assignment_cannot_name_another_organizations_section(client, db_session):
    mine = make_org(db_session, state=OrgState.claimed)
    theirs = make_org(db_session, slug="other-org", state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, mine, admin)
    their_section = make_section(db_session, theirs, name="Their section")

    response = client.post(
        "/clubs/ramapo-trail-conference/assignments",
        json={"person_id": admin.id, "section_id": their_section.id, "start_mile": 11.0, "end_mile": 12.0},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422
    assert db_session.query(MaintainerAssignment).count() == 0


def test_an_assignment_outside_the_organizations_own_sections_is_refused(client, db_session):
    club, person, headers = _self_registered(client, db_session)
    make_section(db_session, club, name="Ours", start_mile=11.0, end_mile=14.3)

    response = client.post(
        "/clubs/totally-real/assignments",
        json={"person_id": person.id, "start_mile": 0.0, "end_mile": 2200.0},
        headers=headers,
    )

    assert response.status_code == 422
    assert db_session.query(MaintainerAssignment).count() == 0


def test_an_assignment_past_the_end_of_its_own_section_is_refused(client, db_session):
    club, person, headers = _self_registered(client, db_session)
    section = make_section(db_session, club, name="Ours", start_mile=11.0, end_mile=14.3)

    response = client.post(
        "/clubs/totally-real/assignments",
        json={"person_id": person.id, "section_id": section.id, "start_mile": 11.0, "end_mile": 40.0},
        headers=headers,
    )

    assert response.status_code == 422


def test_a_role_cannot_name_another_organizations_section(client, db_session):
    mine = make_org(db_session, state=OrgState.claimed)
    theirs = make_org(db_session, slug="other-org", state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, mine, admin)
    their_section = make_section(db_session, theirs, name="Their section")
    role = make_role(db_session, mine)

    created = client.post(
        "/clubs/ramapo-trail-conference/roles",
        json={"name": "Corridor monitor", "category": "stewards", "section_id": their_section.id},
        headers=auth_headers(admin.id),
    )
    updated = client.patch(
        f"/clubs/ramapo-trail-conference/roles/{role.id}",
        json={"section_id": their_section.id},
        headers=auth_headers(admin.id),
    )

    assert created.status_code == 422
    assert updated.status_code == 422


def _supervisor(db_session, org):
    lead = make_role(db_session, org, name="Crew lead")
    make_role(db_session, org, name="Maintainer", reports_to_role_id=lead.id)
    person = make_profile(db_session)
    make_assignment(db_session, org, person, role=lead)
    return person, lead


def test_a_supervisors_roster_sync_writes_proposals_not_live_rows(client, db_session):
    """Every console write carries a stamp, so none can pass for a file-loaded row."""
    org = make_org(db_session, state=OrgState.claimed)
    supervisor, _ = _supervisor(db_session, org)
    volunteer = make_profile(db_session)
    db_session.add(RoleInvite(club_id=org.id, email="vol@club.example", claimed_by=volunteer.id, claimed_at=datetime(2026, 1, 1)))
    db_session.commit()

    client.post(
        "/clubs/ramapo-trail-conference/roster/sync",
        json={"source": "file", "entries": [{"email": "vol@club.example", "active": True}]},
        headers=auth_headers(supervisor.id),
    )

    row = db_session.query(MaintainerAssignment).filter(MaintainerAssignment.maintainer_id == volunteer.id).one()
    assert row.proposed_by == supervisor.id
    assert row.confirmed_at is None


def test_a_proposed_lead_role_does_not_make_somebody_a_supervisor(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    make_admin(db_session, org, make_profile(db_session))
    supervisor, lead = _supervisor(db_session, org)
    make_section(db_session, org)
    friend = make_profile(db_session)

    client.post(
        "/clubs/ramapo-trail-conference/assignments",
        json={"person_id": friend.id, "role_id": lead.id, "start_mile": 11.0, "end_mile": 14.3},
        headers=auth_headers(supervisor.id),
    )

    access = client.get("/clubs/ramapo-trail-conference/access", headers=auth_headers(friend.id)).json()
    assert access["can_manage_volunteers"] is False


# --------------------------------------------------------------------------- #
# 2. A seat at an organization comes from an admin's invitation, and only one.
# --------------------------------------------------------------------------- #


def test_a_supervisors_role_less_invite_does_not_become_an_admin_seat(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    make_admin(db_session, org, make_profile(db_session))
    supervisor, _ = _supervisor(db_session, org)

    invited = client.post(
        "/clubs/ramapo-trail-conference/invites",
        json={"email": "alt@club.example"},
        headers=auth_headers(supervisor.id),
    )
    assert invited.status_code == 201

    alt = make_profile(db_session)
    client.get("/clubs/ramapo-trail-conference/access", headers=auth_headers(alt.id, email="alt@club.example"))

    assert db_session.query(OrgAdmin).filter(OrgAdmin.person_id == alt.id).count() == 0


def test_an_unmatched_roster_role_does_not_become_an_admin_seat(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)

    client.post(
        "/clubs/ramapo-trail-conference/roster/sync",
        json={"source": "file", "entries": [{"email": "vol@club.example", "role_name": "Nonexistent"}]},
        headers=auth_headers(admin.id),
    )
    volunteer = make_profile(db_session)
    client.get("/clubs/ramapo-trail-conference/access", headers=auth_headers(volunteer.id, email="vol@club.example"))

    assert db_session.query(OrgAdmin).filter(OrgAdmin.person_id == volunteer.id).count() == 0


def test_an_admins_invitation_still_becomes_a_seat_its_holder_can_accept(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    client.post(
        "/clubs/ramapo-trail-conference/admins",
        json={"email": "colleague@ramapotrails.org"},
        headers=auth_headers(admin.id),
    )

    colleague = make_profile(db_session)
    headers = auth_headers(colleague.id, email="colleague@ramapotrails.org")
    client.get("/clubs/ramapo-trail-conference/access", headers=headers)
    seat = db_session.query(OrgAdmin).filter(OrgAdmin.person_id == colleague.id).one()
    approved = client.post(f"/clubs/ramapo-trail-conference/admins/{seat.id}/approve", headers=headers)

    assert approved.status_code == 200
    assert client.get("/clubs/ramapo-trail-conference/access", headers=headers).json()["is_admin"] is True


def test_a_seat_no_admin_invited_cannot_be_approved_by_its_holder(client, db_session):
    """Accepting a seat is consent, not authority - the authority is the invitation."""
    org = make_org(db_session, state=OrgState.claimed)
    holder = make_profile(db_session)
    seat = make_admin(db_session, org, holder, approved=False)

    response = client.post(
        f"/clubs/ramapo-trail-conference/admins/{seat.id}/approve",
        headers=auth_headers(holder.id),
    )

    assert response.status_code == 403
    db_session.refresh(seat)
    assert seat.approved_at is None


# --------------------------------------------------------------------------- #
# 3. A nomination is decided by the people at the organization, one each.
# --------------------------------------------------------------------------- #


def _submission(**overrides):
    payload = {
        "website": "https://carolinamountainclub.org",
        "org_name": "Carolina Mountain Club",
        "contacts": [
            {"email": f"{who}@carolinamountainclub.org", "source_page": "https://carolinamountainclub.org/contact"}
            for who in ("volunteers", "maps", "board")
        ],
    }
    payload.update(overrides)
    return payload


def _nominate(client, db_session, **overrides):
    hiker = make_profile(db_session)
    response = client.post("/clubs/nominations", json=_submission(**overrides), headers=auth_headers(hiker.id))
    assert response.status_code == 201, response.text
    return db_session.query(OrgNomination).order_by(OrgNomination.created_at.desc()).first()


def test_one_contacts_link_casts_one_decision(client, db_session):
    nomination = _nominate(client, db_session)
    contact = db_session.query(NominationContact).filter(NominationContact.nomination_id == nomination.id).first()
    assert contact.decision_token

    first = client.post(f"/nominations/{contact.decision_token}/decision", json={"approve": True})
    second = client.post(f"/nominations/{contact.decision_token}/decision", json={"approve": True})

    assert first.status_code == 200
    assert first.json()["approvals_so_far"] == 1
    assert second.status_code == 409


def test_the_shared_link_cannot_decide_anything(client, db_session):
    nomination = _nominate(client, db_session)

    response = client.post(f"/nominations/{nomination.proposal_token}/decision", json={"approve": True})

    assert response.status_code == 404
    assert db_session.query(NominationContact).filter(NominationContact.responded_at.isnot(None)).count() == 0


def test_contacts_off_the_organizations_domain_are_refused(client, db_session):
    hiker = make_profile(db_session)
    contacts = [
        {"email": f"me{i}@elsewhere.example", "source_page": "https://carolinamountainclub.org/contact"} for i in range(3)
    ]

    response = client.post("/clubs/nominations", json=_submission(contacts=contacts), headers=auth_headers(hiker.id))

    assert response.status_code == 422
    assert db_session.query(OrgNomination).count() == 0


def test_a_refusal_from_off_the_domain_is_not_kept_forever(client, db_session):
    """A contact written before the domain rule existed can still decline -
    it just cannot close the door for the organization's own people."""
    nomination = _nominate(client, db_session)
    stranger = NominationContact(
        nomination_id=nomination.id,
        email="someone@elsewhere.example",
        source_page="https://carolinamountainclub.org/contact",
        decision_token="a-legacy-contact-token",
        created_at=datetime(2000, 1, 1),
    )
    db_session.add(stranger)
    db_session.commit()

    response = client.post(
        "/nominations/a-legacy-contact-token/decision",
        json={"approve": False, "never_ask_again": True},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "declined"
    assert db_session.query(NominationRefusal).count() == 0


def test_one_hiker_cannot_submit_nominations_without_limit(client, db_session):
    hiker = make_profile(db_session)
    statuses = [
        client.post(
            "/clubs/nominations",
            json=_submission(org_name=f"Club {i}"),
            headers=auth_headers(hiker.id),
        ).status_code
        for i in range(4)
    ]

    assert statuses == [201, 201, 201, 429]


# --------------------------------------------------------------------------- #
# 4. A GitHub login has the shape of one, or it is not written anywhere.
# --------------------------------------------------------------------------- #


def test_a_login_with_a_newline_in_it_is_not_linked(client, db_session):
    person = make_profile(db_session)
    forged = "mylogin\n* @someone-else"

    response = client.post("/profiles/me/github", headers=auth_headers(person.id, github_login=forged))

    assert response.status_code == 422
    db_session.refresh(person)
    assert person.github_login is None


def test_codeowners_never_renders_a_login_that_is_not_one(db_session):
    """A row written before the check, or by hand, must still not reach the file."""
    org = make_org(db_session, state=OrgState.claimed)
    good = make_profile(db_session, github_login="maria-rtc")
    bad = make_profile(db_session, github_login="evil\n* @attacker")
    make_admin(db_session, org, good)
    make_admin(db_session, org, bad)

    block = codeowners_block(db_session)

    assert block == "/pipeline/reference/orgs/ramapo-trail-conference/ @maria-rtc"


# --------------------------------------------------------------------------- #
# 5. Deleting an account lets go of its GitHub login.
# --------------------------------------------------------------------------- #


def test_a_deleted_accounts_github_login_can_be_linked_again(client, db_session):
    first = make_profile(db_session)
    client.post("/profiles/me/github", headers=auth_headers(first.id, github_login="realuser"))
    client.delete("/profiles/me", headers=auth_headers(first.id))
    db_session.expire_all()
    assert db_session.get(Profile, first.id).github_login is None

    second = make_profile(db_session)
    relinked = client.post("/profiles/me/github", headers=auth_headers(second.id, github_login="realuser"))

    assert relinked.status_code == 200


# --------------------------------------------------------------------------- #
# Minor: a registry signature counts only while its signer is a codeowner.
# --------------------------------------------------------------------------- #


def test_a_signature_from_somebody_who_has_since_declined_does_not_count(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    people = [make_profile(db_session) for _ in range(3)]
    seats = [make_admin(db_session, org, person, is_codeowner=True) for person in people]

    client.post(f"/clubs/{org.slug}/registry/signoff", headers=auth_headers(people[0].id))
    seats[0].approved_at = None
    seats[0].declined_at = datetime(2026, 9, 1)
    db_session.commit()
    client.post(f"/clubs/{org.slug}/registry/signoff", headers=auth_headers(people[1].id))
    body = client.post(f"/clubs/{org.slug}/registry/signoff", headers=auth_headers(people[2].id)).json()

    assert body["signatures"] == 2
    assert body["complete"] is False
