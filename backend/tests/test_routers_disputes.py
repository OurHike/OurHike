"""`GET /disputes` - the corroborated half of FIELD_NOTES.md §4 (#876).

`test_core_disputes.py` holds the rule; these hold the route's own three
decisions:

  - **Only corroborated disputes are served.** One person's "it is gone" is
    already public as a note, in their own words, which is the right weight
    for one observation. The pin's stronger claim needs the threshold.
  - **The identities never leave.** The response carries a count and a date
    and no `reporter_id` - the pair FIELD_NOTES.md §6 withholds.
  - **A maintainer covers a MILE**, not a trail. An assignment is a range,
    and a note with no mile cannot be covered by anybody.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from app.models.club import Club
from app.models.field_note import FieldNote
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Role
from tests.factories import make_profile

_POI = "atc_shelters:spring-1"


def _note(db, reporter_id, *, days_ago, observation="not_found", poi_id=_POI, mile=None):
    note = FieldNote(
        id=str(uuid.uuid4()),
        reporter_id=reporter_id,
        poi_id=poi_id,
        mile=mile,
        observation=observation,
        observed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago),
        posted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        reporter_type="thru",
    )
    db.add(note)
    db.commit()
    return note


def test_a_place_two_hikers_say_is_gone_is_served(client, db_session):
    first = make_profile(db_session, Role.hiker)
    second = make_profile(db_session, Role.hiker)
    _note(db_session, first.id, days_ago=5)
    _note(db_session, second.id, days_ago=1)

    body = client.get("/disputes").json()

    assert [row["poi_id"] for row in body] == [_POI]
    assert body[0]["accounts"] == 2
    assert body[0]["maintainer_said"] is False


def test_one_hiker_alone_is_not_served(client, db_session):
    """Their note is public and says so in their own words. What one person
    cannot do is put the stronger claim on the pin."""
    reporter = make_profile(db_session, Role.hiker)
    _note(db_session, reporter.id, days_ago=1)

    assert client.get("/disputes").json() == []


def test_the_response_carries_no_identities(client, db_session):
    first = make_profile(db_session, Role.hiker)
    second = make_profile(db_session, Role.hiker)
    _note(db_session, first.id, days_ago=5)
    _note(db_session, second.id, days_ago=1)

    row = client.get("/disputes").json()[0]

    # The pair FIELD_NOTES.md §6 withholds: many dated notes along a corridor
    # from one identifier reconstruct a hike.
    assert set(row) == {"poi_id", "accounts", "latest_at", "maintainer_said"}
    for reporter in (first.id, second.id):
        assert reporter not in client.get("/disputes").text


def test_a_covering_maintainer_carries_it_alone(client, db_session):
    club = Club(id=str(uuid.uuid4()), name="NYNJTC")
    db_session.add(club)
    maintainer = make_profile(db_session, Role.maintainer)
    db_session.add(
        MaintainerAssignment(
            id=str(uuid.uuid4()),
            maintainer_id=maintainer.id,
            club_id=club.id,
            start_mile=1400,
            end_mile=1410,
            effective_from=date(2020, 1, 1),
        )
    )
    db_session.commit()
    _note(db_session, maintainer.id, days_ago=2, mile=1405)

    body = client.get("/disputes").json()

    assert body[0]["maintainer_said"] is True
    assert body[0]["accounts"] == 1


def test_a_maintainer_outside_their_miles_is_just_a_hiker(client, db_session):
    club = Club(id=str(uuid.uuid4()), name="NYNJTC")
    db_session.add(club)
    maintainer = make_profile(db_session, Role.maintainer)
    db_session.add(
        MaintainerAssignment(
            id=str(uuid.uuid4()),
            maintainer_id=maintainer.id,
            club_id=club.id,
            start_mile=1400,
            end_mile=1410,
            effective_from=date(2020, 1, 1),
        )
    )
    db_session.commit()
    # Six hundred miles from the stretch they look after.
    _note(db_session, maintainer.id, days_ago=2, mile=800)

    assert client.get("/disputes").json() == []


def test_a_note_with_no_mile_is_covered_by_nobody(client, db_session):
    """An assignment is a range along the centerline. Treating "no mile" as
    covered would hand every maintainer a veto over every unplaced note."""
    club = Club(id=str(uuid.uuid4()), name="NYNJTC")
    db_session.add(club)
    maintainer = make_profile(db_session, Role.maintainer)
    db_session.add(
        MaintainerAssignment(
            id=str(uuid.uuid4()),
            maintainer_id=maintainer.id,
            club_id=club.id,
            start_mile=0,
            end_mile=2200,
            effective_from=date(2020, 1, 1),
        )
    )
    db_session.commit()
    _note(db_session, maintainer.id, days_ago=2, mile=None)

    assert client.get("/disputes").json() == []


def test_a_hidden_note_stops_corroborating(client, db_session):
    """Moderation reaches this too: a note hidden for abuse must not go on
    holding a dispute open from behind the curtain."""
    first = make_profile(db_session, Role.hiker)
    second = make_profile(db_session, Role.hiker)
    _note(db_session, first.id, days_ago=5)
    hidden = _note(db_session, second.id, days_ago=1)
    hidden.hidden_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.commit()

    assert client.get("/disputes").json() == []


def test_notes_with_no_poi_id_are_not_a_place(client, db_session):
    """A note anchored only to coordinates disputes nothing upstream said -
    there is no upstream record for it to contradict."""
    first = make_profile(db_session, Role.hiker)
    second = make_profile(db_session, Role.hiker)
    _note(db_session, first.id, days_ago=5, poi_id=None)
    _note(db_session, second.id, days_ago=1, poi_id=None)

    assert client.get("/disputes").json() == []


def test_browsing_disputes_needs_no_account(client, db_session):
    first = make_profile(db_session, Role.hiker)
    second = make_profile(db_session, Role.hiker)
    _note(db_session, first.id, days_ago=5)
    _note(db_session, second.id, days_ago=1)

    # No Authorization header at all - the state a hiker with no signal and
    # no account is in, which is when this matters most.
    assert client.get("/disputes").status_code == 200
