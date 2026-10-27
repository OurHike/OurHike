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
from datetime import UTC, datetime, timedelta

from app.models.club import Club
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
