"""Who wrote an organization's row, kept apart from who registered it.

#1913 - Deleting the registrant's account turns a self-registered organization
into a maintainer-written one, and lets an accomplice keep an admin seat.
`stood_behind()` and the held-registration revocation both read "a maintainer
wrote this" off `clubs.created_by` being null, and account deletion nulls
`created_by`. The first two tests are the review's two reproductions
(2026-10-27), each of which passed on `main` with the defect in place.
`Club.maintainer_written` now carries the fact, and nothing that deletes an
account touches it.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.assignments import assignments_covering
from app.models.club import Club, OrgAdmin, OrgState, VerifiedBy
from app.models.maintainer_assignment import MaintainerAssignment
from load_assignments import apply, parse
from tests.factories import make_org, make_profile
from tests.tokens import auth_headers


def _new_id() -> str:
    return str(uuid.uuid4())


def test_deleting_the_registrants_account_gives_a_self_registered_org_no_weight(client):
    """Registered at a domain the registrant holds, so `claimed` at once, and
    its admin puts a second account on every mile of the A.T. None of that
    counts with hikers, before the deletion or after it."""
    registrant, volunteer, thanker = _new_id(), _new_id(), _new_id()
    registrant_headers = auth_headers(registrant, email="chair@evil-trails.org")

    registered = client.post(
        "/clubs",
        json={"name": "Evil Trails", "slug": "evil-trails", "domain": "evil-trails.org"},
        headers=registrant_headers,
    )
    assert registered.status_code == 201 and registered.json()["state"] == "claimed", registered.text
    park = client.post("/clubs/evil-trails/registry/parks", json={"name": "Everything"}, headers=registrant_headers)
    trail = client.post(
        f"/clubs/evil-trails/registry/parks/{park.json()['id']}/trails", json={"name": "AT"}, headers=registrant_headers
    )
    section = client.post(
        f"/clubs/evil-trails/registry/trails/{trail.json()['id']}/sections",
        json={"name": "All of it", "start_mile": 0, "end_mile": 2200},
        headers=registrant_headers,
    )
    assert section.status_code == 201, section.text
    assert client.get("/profiles/me", headers=auth_headers(volunteer)).status_code == 200
    assigned = client.post(
        "/clubs/evil-trails/assignments",
        json={"person_id": volunteer, "start_mile": 0, "end_mile": 2200, "effective_from": "2000-01-01"},
        headers=registrant_headers,
    )
    assert assigned.status_code == 201, assigned.text

    thanks = client.post(
        "/reports",
        json={
            "type": "thanks",
            "reporter_type": "thru",
            "mile": 500.0,
            "lat": 37.1,
            "lon": -80.5,
            "note": "Thank you for the gap on the 12th",
            "authored_at": (datetime.now(UTC) - timedelta(days=7)).isoformat(),
        },
        headers=auth_headers(thanker),
    )
    assert thanks.status_code == 201, thanks.text
    for hiker in (_new_id(), _new_id()):
        reported = client.post(
            "/field-notes",
            json={"poi_id": "spring-500", "mile": 500.0, "observation": "not_found", "reporter_type": "thru"},
            headers=auth_headers(hiker),
        )
        assert reported.status_code == 201, reported.text
    flowing = client.post(
        "/field-notes",
        json={"poi_id": "spring-500", "mile": 500.0, "observation": "flowing", "reporter_type": "maintainer"},
        headers=auth_headers(volunteer),
    )
    assert flowing.status_code == 201, flowing.text

    def no_weight() -> None:
        assert client.get("/reports/thanks", headers=auth_headers(volunteer)).json() == []
        assert client.get("/maintainer-assignments", params={"mile": 500}).json() == []
        assert [d["poi_id"] for d in client.get("/disputes").json()] == ["spring-500"]

    no_weight()
    assert client.delete("/profiles/me", headers=registrant_headers).status_code == 200
    no_weight()


def test_deleting_the_registrants_account_does_not_spare_the_seats_they_handed_out(client):
    """A held registration: a gmail address names a real organization's
    domain, offers a seat to an accomplice, then deletes its own account. When
    the real chair proves the domain, every seat the registration handed out
    goes, as #1641's fix intended (Backend and org-console findings the v1.3.2
    release review deferred, all blocking a production backend (#600))."""
    registrant, accomplice, chair = _new_id(), _new_id(), _new_id()
    registrant_headers = auth_headers(registrant, email="someone@gmail.com")
    accomplice_headers = auth_headers(accomplice, email="accomplice@gmail.com")
    chair_headers = auth_headers(chair, email="chair@ramapotrails.org")

    registered = client.post(
        "/clubs",
        json={
            "name": "Ramapo Trail Conference",
            "slug": "ramapo",
            "domain": "ramapotrails.org",
            "admins": [{"email": "chair@ramapotrails.org"}, {"email": "accomplice@gmail.com"}],
        },
        headers=registrant_headers,
    )
    assert registered.status_code == 201 and registered.json()["state"] == "pending", registered.text

    client.get("/clubs/ramapo/access", headers=accomplice_headers)
    seat = next(a for a in client.get("/clubs/ramapo").json()["admins"] if a["person_id"] == accomplice)
    assert client.post(f"/clubs/ramapo/admins/{seat['id']}/approve", headers=accomplice_headers).status_code == 200

    assert client.delete("/profiles/me", headers=registrant_headers).status_code == 200

    client.get("/clubs/ramapo/access", headers=chair_headers)
    mine = next(a for a in client.get("/clubs/ramapo").json()["admins"] if a["person_id"] == chair)
    approved = client.post(f"/clubs/ramapo/admins/{mine['id']}/approve", headers=chair_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "claimed"

    assert client.get("/clubs/ramapo/access", headers=accomplice_headers).json()["is_admin"] is False
    assert client.get("/clubs/ramapo/export", headers=accomplice_headers).status_code == 403


def test_the_reviewed_file_is_what_marks_a_club_maintainer_written(db_session):
    maintainer = make_profile(db_session)
    document = {
        "clubs": [{"id": "nbatc", "name": "Natural Bridge ATC", "region": "Central Virginia"}],
        "assignments": [
            {
                "maintainer_id": maintainer.id,
                "club_id": "nbatc",
                "start_mile": 728.0,
                "end_mile": 754.5,
                "effective_from": "2026-01-01",
            }
        ],
    }

    apply(db_session, *parse(document))
    db_session.commit()

    assert db_session.get(Club, "nbatc").maintainer_written is True


def test_a_registration_through_the_console_is_not_maintainer_written(client, db_session):
    registered = client.post(
        "/clubs",
        json={"name": "Ramapo Trail Conference", "slug": "ramapo", "domain": "ramapotrails.org"},
        headers=auth_headers(_new_id(), email="chair@ramapotrails.org"),
    )
    assert registered.status_code == 201, registered.text

    assert db_session.query(Club).one().maintainer_written is False


def test_claiming_a_maintainers_org_hands_it_to_whoever_proved_the_domain(client, db_session):
    """After a claim, the admins are whoever proved the domain, which no
    maintainer reviewed. `created_by` used to say so, and the flag says so now."""
    make_org(db_session)
    claimed = client.post(
        "/clubs/ramapo-trail-conference/claim",
        json={"title": "Trails chair"},
        headers=auth_headers(_new_id(), email="maria@ramapotrails.org"),
    )
    assert claimed.status_code == 200, claimed.text

    db_session.expire_all()
    assert db_session.query(Club).one().maintainer_written is False


def _console_confirmed_assignment(db_session, club, *, start_mile=400.0, end_mile=600.0):
    """An assignment an admin confirmed in the console: both stamps set, which
    is what makes it count only through `stood_behind()`'s second condition."""
    volunteer, admin = make_profile(db_session), make_profile(db_session)
    now = datetime.now(UTC).replace(tzinfo=None)
    assignment = MaintainerAssignment(
        id=_new_id(),
        maintainer_id=volunteer.id,
        club_id=club.id,
        start_mile=start_mile,
        end_mile=end_mile,
        effective_from=date(2020, 1, 1),
        proposed_by=admin.id,
        confirmed_by=admin.id,
        confirmed_at=now,
    )
    db_session.add(assignment)
    db_session.commit()
    return assignment


def test_a_console_confirmed_assignment_counts_at_an_org_a_maintainer_wrote(db_session):
    """The positive half of `stood_behind()`'s second condition, which no test
    pinned: deleting it left 353 tests green (the 2026-10-29 review)."""
    club = make_org(db_session)
    assignment = _console_confirmed_assignment(db_session, club)

    covering = assignments_covering(db_session, 500.0, date.today())

    assert [row.id for row, _, _ in covering] == [assignment.id]


@pytest.mark.parametrize(
    "fields",
    [
        {"maintainer_written": False},
        # A claim by code from before the flag existed leaves it true, and a
        # claimed organization always has `verified_by`.
        {"state": OrgState.claimed, "maintainer_written": True, "verified_by": VerifiedBy.email},
    ],
    ids=["self-registered", "claimed-by-old-code"],
)
def test_a_console_confirmed_assignment_does_not_count_anywhere_else(db_session, fields):
    club = make_org(db_session, **fields)
    _console_confirmed_assignment(db_session, club)

    assert assignments_covering(db_session, 500.0, date.today()) == []


def _held_registration(client, chair_email="chair@ramapotrails.org"):
    """A gmail address registering a real organization's domain and naming the
    real chair: `pending` until somebody at the domain agrees."""
    registered = client.post(
        "/clubs",
        json={
            "name": "Ramapo Trail Conference",
            "slug": "ramapo",
            "domain": "ramapotrails.org",
            "admins": [{"email": chair_email}],
        },
        headers=auth_headers(_new_id(), email="someone@gmail.com"),
    )
    assert registered.status_code == 201 and registered.json()["state"] == "pending", registered.text


def test_approving_a_held_registration_clears_the_flag(client, db_session):
    """The other release of a held registration besides `claim_org`, which used
    to leave the flag as the backfill found it."""
    _held_registration(client)
    db_session.query(Club).update({Club.maintainer_written: True})
    db_session.commit()
    chair = _new_id()
    chair_headers = auth_headers(chair, email="chair@ramapotrails.org")
    client.get("/clubs/ramapo/access", headers=chair_headers)
    mine = next(a for a in client.get("/clubs/ramapo").json()["admins"] if a["person_id"] == chair)

    approved = client.post(f"/clubs/ramapo/admins/{mine['id']}/approve", headers=chair_headers)

    assert approved.status_code == 200 and approved.json()["state"] == "claimed", approved.text
    db_session.expire_all()
    assert db_session.query(Club).one().maintainer_written is False


def test_a_domain_holder_seated_from_the_invitation_can_still_claim(client, db_session):
    """Signing in seated the chair from the registration's invitation, and the
    claim used to insert a second seat for them: a 500 on
    `uq_club_admins_club_person`, found by the 2026-10-29 review on `main`."""
    _held_registration(client)
    chair = _new_id()
    chair_headers = auth_headers(chair, email="chair@ramapotrails.org")
    client.get("/clubs/ramapo/access", headers=chair_headers)

    claimed = client.post("/clubs/ramapo/claim", json={"title": "Trails chair"}, headers=chair_headers)

    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["state"] == "claimed"
    seats = db_session.query(OrgAdmin).filter(OrgAdmin.person_id == chair).all()
    assert len(seats) == 1 and seats[0].approved_at is not None and seats[0].is_codeowner
