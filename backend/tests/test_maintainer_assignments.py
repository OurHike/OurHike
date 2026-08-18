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
from tests.factories import make_profile
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
    held = _assign(db_session, maintainer=pat, club=club, start=1040, end=1050, frm=date(2026, 1, 1))

    response = client.get("/maintainer-assignments?mile=1043.2")

    assert response.status_code == 200
    # Assignments are matched by their row id: the response deliberately
    # carries no maintainer_id for anyone to compare (#641).
    assert [a["id"] for a in response.json()] == [held.id]


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
    pats = _assign(db_session, maintainer=pat, club=club, start=1040, end=1050, frm=date(2026, 1, 1))
    sams = _assign(db_session, maintainer=sam, club=club, start=1045, end=1055, frm=date(2026, 1, 1))

    found = {a["id"] for a in client.get("/maintainer-assignments?mile=1047").json()}

    assert found == {pats.id, sams.id}


def test_resolve_as_of_a_past_date_returns_who_held_it_then(client, db_session):
    """The case the whole versioned model exists for: a thanks written in
    June about work done in June, synced in August, after a July hand-off."""
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    pats = _assign(
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

    assert [a["id"] for a in june] == [pats.id]


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
    sams = _assign(db_session, maintainer=sam, club=club, start=1040, end=1050, frm=date(2021, 1, 1))

    current = client.get("/maintainer-assignments?mile=1043").json()

    assert [a["id"] for a in current] == [sams.id]


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
    # And not merely the name: the account id is a stable join key tying a
    # person to a place and a schedule, and it is not in the response at all,
    # consented or otherwise (#641). Consent gates the label; nothing public
    # carries the id. Same decision as #252 (reports) and #430 (closures).
    assert "maintainer_id" not in found


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
    moderator = make_profile(db_session, Role.club_admin, display_name="Mod")

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
    moderator = make_profile(db_session, Role.club_admin, display_name="Mod")

    created = client.post("/reports", json=_THANKS, headers=auth_headers(str(uuid.uuid4()))).json()
    response = client.post(f"/reports/{created['id']}/dismiss", headers=auth_headers(moderator.id))

    assert response.status_code == 200


def test_thanks_is_a_real_member_of_the_report_type_enum(client):
    assert ReportType.thanks.value == "thanks"


# --- Receiving a thanks: resolution, and the reader `club_only` never had ---
#
# #249 filed four gaps as one flow, because fixing them separately risks
# fixing none of them. The client promised a server-side resolution nothing
# performed; the server could not have resolved anyway without a mile (#244);
# `club_only` appeared in no query, so a thanks was readable by exactly one
# person forever - its author; and the tables it resolves against had no way
# in.

_JUNE = date(2026, 6, 1)
_JULY = date(2026, 7, 1)


def _thanks_at(client, mile, authored, *, hiker=None, **extra):
    """File a thanks at a mile, authored on a date. Returns the response body."""
    payload = dict(
        _THANKS,
        mile=mile,
        authored_at=f"{authored.isoformat()}T12:00:00+00:00",
        **extra,
    )
    return client.post("/reports", json=payload, headers=auth_headers(hiker or str(uuid.uuid4()))).json()


def test_a_thanks_resolves_to_whoever_had_the_stretch(client, db_session):
    """The resolution `maintainerLookup.ts` has been promising all along.

    "The authoritative answer is worked out server-side when the thanks is
    finally received, from its location and authored date" - which nothing
    performed until now.
    """
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE)

    body = _thanks_at(client, 1043, _JUNE)

    assert body["maintainer_id"] == pat.id
    assert body["club_id"] == club.id


def test_it_resolves_against_the_authored_date_not_today(client, db_session):
    """The part that is easy to get wrong, and the reason assignments are
    versioned at all.

    A thanks written in June about a stretch reassigned in July, syncing from
    an outbox in August, belongs to JUNE's maintainer. Resolving against now
    would hand a stranger someone else's credit and quietly rob the person
    who earned it.
    """
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE, to=date(2026, 6, 30))
    _assign(db_session, maintainer=sam, club=club, start=1000, end=1100, frm=_JULY)

    body = _thanks_at(client, 1043, _JUNE)

    assert body["maintainer_id"] == pat.id


def test_a_hiker_who_knows_the_name_is_not_overruled_by_the_lookup(client, db_session):
    """SAYING_THANKS.md's "optionally tagging the maintainer responsible".

    Somebody who knows who they are thanking has said something the location
    cannot say, and a lookup that overwrote it would be the app correcting a
    hiker about their own gratitude.
    """
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(db_session, maintainer=sam, club=club, start=1000, end=1100, frm=_JUNE)

    body = _thanks_at(client, 1043, _JUNE, maintainer_id=pat.id)

    assert body["maintainer_id"] == pat.id
    # ...and the half they left blank is still resolved.
    assert body["club_id"] == club.id


def test_overlapping_stretches_name_the_club_but_not_a_person(client, db_session):
    """Resolution returns zero or more, never exactly one.

    Two maintainers cover a boundary; one foreign key cannot hold both, and
    picking one would credit a coin toss. The club is still unambiguous, and
    club-level is the documented default. Delivery reaches both - see below.
    """
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1050, frm=_JUNE)
    _assign(db_session, maintainer=sam, club=club, start=1050, end=1100, frm=_JUNE)

    body = _thanks_at(client, 1050, _JUNE)

    assert body["maintainer_id"] is None
    assert body["club_id"] == club.id


def test_a_thanks_with_no_mile_resolves_to_nobody_rather_than_guessing(client, db_session):
    """Still a complete thanks. Inventing a position for it would credit a
    volunteer for a stretch nobody said this was about."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE)

    body = client.post("/reports", json=_THANKS, headers=auth_headers(str(uuid.uuid4()))).json()

    assert body["maintainer_id"] is None
    assert body["club_id"] is None


def test_a_condition_report_cannot_carry_a_profile_id_it_names_itself(client, db_session):
    """The hole `ReportOut` already documented, closed.

    These are foreign keys to real people and they were copied from the
    request for EVERY type - so a `blowdown`, which is `public`, could arrive
    carrying any profile id a caller cared to name, and `maintainer_id` was a
    second `reporter_id` nobody had noticed.
    """
    club = _club(db_session)
    pat = _maintainer(db_session)
    payload = {
        "type": "blowdown",
        "reporter_type": "thru",
        "lat": 37.9,
        "lon": -79.1,
        "maintainer_id": pat.id,
        "club_id": club.id,
    }

    body = client.post("/reports", json=payload, headers=auth_headers(pat.id)).json()

    assert body["maintainer_id"] is None
    assert body["club_id"] is None


# --- GET /reports/thanks: the delivery ------------------------------------


def _inbox(client, viewer_id):
    response = client.get("/reports/thanks", headers=auth_headers(viewer_id))
    assert response.status_code == 200
    return response.json()


def test_a_maintainer_sees_a_thanks_for_their_own_stretch(client, db_session):
    """Before this, `club_only` appeared in no query at all: the public list
    excludes it, the moderation queue excludes `thanks` on purpose, and
    nothing else read it."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE)
    filed = _thanks_at(client, 1043, _JUNE)

    assert [row["id"] for row in _inbox(client, pat.id)] == [filed["id"]]


def test_both_maintainers_of_an_overlap_see_it(client, db_session):
    """The case a single `maintainer_id` cannot express, and the reason
    delivery re-asks the question rather than reading that column.

    "Two is also normal, and both hear about it" - SAYING_THANKS.md. Under
    delivery-by-column this thanks would have reached neither, because
    resolution correctly refused to pick one of them.
    """
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1050, frm=_JUNE)
    _assign(db_session, maintainer=sam, club=club, start=1050, end=1100, frm=_JUNE)
    filed = _thanks_at(client, 1050, _JUNE)

    assert [row["id"] for row in _inbox(client, pat.id)] == [filed["id"]]
    assert [row["id"] for row in _inbox(client, sam.id)] == [filed["id"]]


def test_a_maintainer_of_another_stretch_sees_nothing(client, db_session):
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE)
    _assign(db_session, maintainer=sam, club=club, start=1, end=2, frm=_JUNE)
    _thanks_at(client, 1043, _JUNE)

    # Sam's own stretch is nowhere near it - but they share a club, which is
    # the club-level default, so what they must not see is a thanks addressed
    # to a club they are not in.
    other_club = _club(db_session, "Other Club")
    stranger = _maintainer(db_session, "Alex")
    _assign(db_session, maintainer=stranger, club=other_club, start=1, end=2, frm=_JUNE)

    assert _inbox(client, stranger.id) == []


def test_the_maintainer_who_did_the_work_keeps_it_after_handing_over(client, db_session):
    """The claim this makes, precisely (#658): Pat is the resolved
    INDIVIDUAL, and stays it after handing over. It does not claim the
    successor never sees the thanks - Sam shares the club and receives it
    as club mail at the endpoint level, which is the club-level default,
    not a leak. The old headline ("the one who took over does not inherit
    it") read as the stronger claim and asserted only this one.

    Same rule as resolution, from the delivery end: the assignment's own
    dates are checked against when the thanks was WRITTEN.
    """
    club = _club(db_session)
    pat = _maintainer(db_session, "Pat")
    sam = _maintainer(db_session, "Sam")
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE, to=date(2026, 6, 30))
    _assign(db_session, maintainer=sam, club=club, start=1000, end=1100, frm=_JULY)
    filed = _thanks_at(client, 1043, _JUNE)

    assert [row["id"] for row in _inbox(client, pat.id)] == [filed["id"]]
    # Sam shares the club, so they see it as club mail rather than as theirs -
    # which is the club-level default, not a leak. What they must not be is
    # the resolved individual.
    assert filed["maintainer_id"] == pat.id


def test_a_thanks_written_on_the_last_day_of_an_assignment_is_still_theirs(client, db_session):
    """`effective_to` is a whole day and `timestamp` is a moment, so the
    delivery bound is half-open on the upper end. A thanks written at noon on
    a maintainer's last day belongs to them, not to nobody."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    last = date(2026, 6, 30)
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE, to=last)
    filed = _thanks_at(client, 1043, last)

    assert [row["id"] for row in _inbox(client, pat.id)] == [filed["id"]]


def test_a_named_maintainer_with_no_assignment_still_gets_it(client, db_session):
    """Being tagged by name stands alone - a maintainer between sections, or
    one whose club has not been loaded into the table yet."""
    pat = _maintainer(db_session)
    filed = _thanks_at(client, 1043, _JUNE, maintainer_id=pat.id)

    assert [row["id"] for row in _inbox(client, pat.id)] == [filed["id"]]


def test_a_dismissed_thanks_leaves_every_inbox_it_was_delivered_to(client, db_session):
    """Dismissal is the abuse-removal path - the one moderation action a
    thanks can receive - and this inbox is the only place a thanks is ever
    delivered. It used to be a no-op for its only audience (#642): the status
    changed and the delivery query never read it, so the person the abuse
    targeted kept it at the top of their inbox forever."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    moderator = make_profile(db_session, Role.club_admin, display_name="Mod")
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE)
    filed = _thanks_at(client, 1043, _JUNE)
    assert [row["id"] for row in _inbox(client, pat.id)] == [filed["id"]]

    dismissed = client.post(f"/reports/{filed['id']}/dismiss", headers=auth_headers(moderator.id))

    assert dismissed.status_code == 200
    assert _inbox(client, pat.id) == []


def test_a_club_thanks_does_not_follow_someone_out_of_the_club(client, db_session):
    """Club delivery is a standing relationship, not a memory (#642). An
    assignment that ended years ago used to keep delivering the club's mail -
    club_only content flowing to somebody outside the club. The stretch
    clause is deliberately untouched: a thanks for their own old work still
    arrives, because that one is judged by when the work was done."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=date(2019, 1, 1), to=date(2020, 12, 31))
    _thanks_at(client, 4.2, _JUNE, club_id=club.id)

    assert _inbox(client, pat.id) == []


def test_a_hiker_with_no_assignments_gets_an_empty_inbox_not_a_403(client, db_session):
    """The true answer, rather than an error about a resource that does not
    concern them."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE)
    _thanks_at(client, 1043, _JUNE)

    assert _inbox(client, str(uuid.uuid4())) == []


def test_the_inbox_needs_an_account(client):
    """Unlike every browsing endpoint in this app, and for the reason
    `club_only` exists: "who is this addressed to" has no anonymous answer."""
    assert client.get("/reports/thanks").status_code == 401


def test_only_thanks_reach_the_inbox(client, db_session):
    """A blowdown at the same mile is trail work, not gratitude, and it has
    its own delivery - the moderation queue."""
    club = _club(db_session)
    pat = _maintainer(db_session)
    _assign(db_session, maintainer=pat, club=club, start=1000, end=1100, frm=_JUNE)
    client.post(
        "/reports",
        json={"type": "blowdown", "reporter_type": "thru", "lat": 37.9, "lon": -79.1, "mile": 1043},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert _inbox(client, pat.id) == []


def test_the_inbox_path_is_not_swallowed_by_the_report_detail_route(client, db_session):
    """`/reports/thanks` and `/reports/{report_id}` are the same shape, so
    declaration order is what keeps "thanks" from being read as an id. A 404
    here would be that ordering having been lost in a later edit."""
    pat = _maintainer(db_session)

    assert client.get("/reports/thanks", headers=auth_headers(pat.id)).status_code == 200
