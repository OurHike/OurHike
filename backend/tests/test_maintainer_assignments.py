"""Tests for maintainer assignments and the `thanks` report type.

See ../../features/SAYING_THANKS.md and the `MaintainerAssignment` section
of ../../features/VOLUNTEERING.md.

Two behaviours here carry the design's real weight:

1. Assignments are VERSIONED, and lookups are always as-of a date. A thanks
   written in June, about a section reassigned in July, syncing from an
   outbox in August belongs to the June maintainer. Resolving against "now"
   hands a stranger someone else's credit.

2. A thanks is not a condition report. It never enters the moderation queue
   (there is nothing to verify about gratitude), and it is `club_only` -
   neither a public map pin nor `internal_only`, which was named for the
   `bad_hikers` safety case and means a different audience entirely.
"""

import uuid
from datetime import date

from app.models.club import Club
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Profile, Role
from app.models.report import ReportType, Visibility
from tests.tokens import auth_headers


def _club(db, name: str = "Mountain Club") -> Club:
    club = Club(id=str(uuid.uuid4()), name=name, region="Central Virginia")
    db.add(club)
    db.commit()
    return club


def _maintainer(db, name: str = "Pat") -> Profile:
    profile = Profile(id=str(uuid.uuid4()), role=Role.maintainer, display_name=name)
    db.add(profile)
    db.commit()
    return profile


def _assign(db, *, maintainer, club, start, end, frm, to=None, creditable=False):
    assignment = MaintainerAssignment(
        id=str(uuid.uuid4()),
        maintainer_id=maintainer.id,
        club_id=club.id,
        start_mile=start,
        end_mile=end,
        effective_from=frm,
        effective_to=to,
        publicly_creditable=creditable,
    )
    db.add(assignment)
    db.commit()
    return assignment


# --- Resolution by location and date ------------------------------------


def test_resolve_returns_the_maintainer_covering_that_mile(client, db_session):
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    _assign(db_session, maintainer=pat, club=club, start=1040, end=1050, frm=date(2026, 1, 1))

    response = client.get("/maintainer-assignments?mile=1043.2")

    assert response.status_code == 200
    assert [a["maintainer_id"] for a in response.json()] == [pat.id]


def test_resolve_excludes_a_mile_outside_the_assigned_stretch(client, db_session):
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1040, end=1050, frm=date(2026, 1, 1))

    assert client.get("/maintainer-assignments?mile=1200").json() == []


def test_resolve_returns_an_empty_list_for_an_unassigned_stretch(client):
    """Zero is a normal answer, not an error - the thanks falls back to the
    club, or is simply held with its location."""
    response = client.get("/maintainer-assignments?mile=500")

    assert response.status_code == 200
    assert response.json() == []


def test_resolve_returns_every_maintainer_on_an_overlapping_stretch(client, db_session):
    """Stretches overlap at boundaries and during hand-offs; both hear about
    it rather than one being arbitrarily picked."""
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(db_session, maintainer=pat, club=club, start=1040, end=1050, frm=date(2026, 1, 1))
    _assign(db_session, maintainer=sam, club=club, start=1045, end=1055, frm=date(2026, 1, 1))

    found = {a["maintainer_id"] for a in client.get("/maintainer-assignments?mile=1047").json()}

    assert found == {pat.id, sam.id}


def test_resolve_as_of_a_past_date_returns_who_held_it_then(client, db_session):
    """The case the whole versioned model exists for: a thanks written in
    June about work done in June, synced in August, after a July hand-off."""
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(
        db_session,
        maintainer=pat,
        club=club,
        start=1040,
        end=1050,
        frm=date(2026, 1, 1),
        to=date(2026, 6, 30),
    )
    _assign(db_session, maintainer=sam, club=club, start=1040, end=1050, frm=date(2026, 7, 1))

    june = client.get("/maintainer-assignments?mile=1043&as_of=2026-06-15").json()

    assert [a["maintainer_id"] for a in june] == [pat.id]


def test_resolve_without_a_date_uses_the_current_assignment(client, db_session):
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(
        db_session,
        maintainer=pat,
        club=club,
        start=1040,
        end=1050,
        frm=date(2020, 1, 1),
        to=date(2020, 12, 31),
    )
    _assign(db_session, maintainer=sam, club=club, start=1040, end=1050, frm=date(2021, 1, 1))

    current = client.get("/maintainer-assignments?mile=1043").json()

    assert [a["maintainer_id"] for a in current] == [sam.id]


def test_resolve_excludes_an_assignment_that_had_not_started_yet(client, db_session):
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1040, end=1050, frm=date(2030, 1, 1))

    assert client.get("/maintainer-assignments?mile=1043&as_of=2026-06-15").json() == []


def test_resolve_needs_no_account(client, db_session):
    """Same rule as every other browsing endpoint - reading needs no login."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1040, end=1050, frm=date(2026, 1, 1))

    assert client.get("/maintainer-assignments?mile=1043").status_code == 200


# --- Individual attribution is opt-in -----------------------------------


def test_resolve_withholds_a_maintainer_name_unless_they_opted_in(client, db_session):
    """SAYING_THANKS.md's privacy default. A volunteer working a remote
    section on a predictable schedule did not sign up to have their name
    and whereabouts shown to strangers."""
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    _assign(
        db_session,
        maintainer=pat,
        club=club,
        start=1040,
        end=1050,
        frm=date(2026, 1, 1),
        creditable=False,
    )

    [found] = client.get("/maintainer-assignments?mile=1043").json()

    assert found["display_name"] is None
    assert found["club_name"] == "Mountain Club"


def test_resolve_names_a_maintainer_who_opted_in(client, db_session):
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    _assign(
        db_session,
        maintainer=pat,
        club=club,
        start=1040,
        end=1050,
        frm=date(2026, 1, 1),
        creditable=True,
    )

    [found] = client.get("/maintainer-assignments?mile=1043").json()

    assert found["display_name"] == "Pat"


# --- The `thanks` report type -------------------------------------------


_THANKS = {
    "type": "thanks",
    "reporter_type": "thru",
    "lat": 37.9,
    "lon": -79.1,
    "note": "Whoever cleared the blowdowns through here - thank you.",
}


def test_a_thanks_is_club_only_never_public(client):
    user_id = str(uuid.uuid4())

    response = client.post("/reports", json=_THANKS, headers=auth_headers(user_id))

    assert response.status_code == 201
    assert response.json()["visibility"] == Visibility.club_only.value


def test_a_thanks_never_appears_in_the_public_report_list(client):
    """It is not a hazard and does not belong as a pin on the safety map."""
    client.post("/reports", json=_THANKS, headers=auth_headers(str(uuid.uuid4())))

    assert [r for r in client.get("/reports").json() if r["type"] == "thanks"] == []


def test_a_thanks_can_name_the_maintainer_it_is_for(client, db_session):
    club = _club(db_session)
    pat = _maintainer(db_session)
    payload = dict(_THANKS, maintainer_id=pat.id, club_id=club.id)

    body = client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4()))).json()

    assert body["maintainer_id"] == pat.id
    assert body["club_id"] == club.id


def test_a_thanks_with_no_attribution_at_all_is_still_accepted(client):
    """ "Someone cleared forty blowdowns and I have no idea who" is a
    complete thanks - it resolves by location rather than being refused."""
    response = client.post("/reports", json=_THANKS, headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 201
    assert response.json()["maintainer_id"] is None


def test_a_condition_report_is_unaffected_and_still_public(client):
    payload = {"type": "blowdown", "reporter_type": "thru", "lat": 37.9, "lon": -79.1}

    body = client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4()))).json()

    assert body["visibility"] == Visibility.public.value


def test_bad_hikers_stays_internal_only_not_club_only(client):
    """The two non-public values mean different audiences: internal_only
    goes to safety moderators, club_only to the club. Adding one must not
    have quietly reassigned the other."""
    payload = {"type": "bad_hikers", "reporter_type": "thru", "lat": 37.9, "lon": -79.1}

    body = client.post("/reports", json=payload, headers=auth_headers(str(uuid.uuid4()))).json()

    assert body["visibility"] == Visibility.internal_only.value


# --- A thanks stays out of the moderation queue -------------------------


def test_verifying_a_thanks_is_refused(client, db_session):
    """There is nothing to verify about gratitude, so the action is not
    merely hidden in the UI - the server refuses it."""
    moderator = Profile(id=str(uuid.uuid4()), role=Role.club_admin, display_name="Mod")
    db_session.add(moderator)
    db_session.commit()

    created = client.post("/reports", json=_THANKS, headers=auth_headers(str(uuid.uuid4()))).json()
    response = client.post(
        f"/reports/{created['id']}/verify",
        json={"severity": "normal"},
        headers=auth_headers(moderator.id),
    )

    assert response.status_code == 409


def test_a_thanks_can_still_be_dismissed_so_abuse_has_a_removal_path(client, db_session):
    """Not verification - removal. Someone will eventually write something
    unkind in a thanks box, and hiding it must stay possible."""
    moderator = Profile(id=str(uuid.uuid4()), role=Role.club_admin, display_name="Mod")
    db_session.add(moderator)
    db_session.commit()

    created = client.post("/reports", json=_THANKS, headers=auth_headers(str(uuid.uuid4()))).json()
    response = client.post(f"/reports/{created['id']}/dismiss", headers=auth_headers(moderator.id))

    assert response.status_code == 200


def test_thanks_is_a_real_member_of_the_report_type_enum(client):
    assert ReportType.thanks.value == "thanks"
