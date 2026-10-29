"""`GET /disputes` - the corroborated half of FIELD_NOTES.md §4 (#876).

`test_core_disputes.py` holds the rule; these hold the route's own three
decisions:

  - **Only corroborated disputes are served.** One person's "it is gone" is
    already public as a note, in their own words, which is the right weight
    for one observation. The pin's stronger claim needs the threshold.
  - **The identities never leave.** The response carries a count and a date
    and no `reporter_id` - the pair FIELD_NOTES.md §6 withholds.
  - **A maintainer covers a WAYPOINT'S MILE**, not a trail, and not the mile
    written on the note (#1917 - A maintainer's note settles a water dispute
    anywhere on the trail, because the covering check reads the mile the
    note's author typed, not where the waypoint is). An assignment is a
    range, the waypoint's mile comes from `waypoint_miles`, and a waypoint
    with no known mile cannot be covered by anybody.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from app.models.club import Club
from app.models.field_note import FieldNote
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Role
from app.models.waypoint_mile import WaypointMile
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


def _waypoint(db, mile, poi_id=_POI):
    """Where the published export puts the waypoint, as `load_waypoint_miles.py` loads it."""
    db.add(WaypointMile(poi_id=poi_id, mile=mile, loaded_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db.commit()


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
    _waypoint(db_session, 1405)
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
    _waypoint(db_session, 800)
    _note(db_session, maintainer.id, days_ago=2, mile=800)

    assert client.get("/disputes").json() == []


def _maintainer_of(db, start_mile, end_mile):
    club = Club(id=str(uuid.uuid4()), name="NYNJTC")
    db.add(club)
    maintainer = make_profile(db, Role.maintainer)
    db.add(
        MaintainerAssignment(
            id=str(uuid.uuid4()),
            maintainer_id=maintainer.id,
            club_id=club.id,
            start_mile=start_mile,
            end_mile=end_mile,
            effective_from=date(2020, 1, 1),
        )
    )
    db.commit()
    return maintainer


def test_a_maintainers_not_found_on_an_unloaded_waypoint_still_puts_it_in_dispute(client, db_session):
    """No `waypoint_miles` row - every waypoint before the first load, and
    each one a release adds until the next. A covering maintainer's lone
    `not_found` still marks it, from the mile they typed: a wrong one sends a
    hiker on with extra water, and staying silent is the missing warning."""
    maintainer = _maintainer_of(db_session, 1400, 1410)
    _note(db_session, maintainer.id, days_ago=2, mile=1405)

    body = client.get("/disputes").json()

    assert [row["poi_id"] for row in body] == [_POI]
    assert body[0]["maintainer_said"] is True


def test_a_maintainers_confirmation_on_an_unloaded_waypoint_does_not_clear_a_dispute(client, db_session):
    """The other direction stays shut without a loaded mile: one maintainer's
    "flowing" on a spring two hikers could not find, claiming a mile inside
    their stretch, is #1917's harm wherever the spring really is."""
    maintainer = _maintainer_of(db_session, 1400, 1410)
    for hiker in (make_profile(db_session, Role.hiker), make_profile(db_session, Role.hiker)):
        _note(db_session, hiker.id, days_ago=3)
    _note(db_session, maintainer.id, days_ago=1, observation="flowing", mile=1405)

    body = client.get("/disputes").json()

    assert [row["poi_id"] for row in body] == [_POI], "an unplaced waypoint's dispute needs two confirmations"
    assert body[0]["maintainer_said"] is False


def test_a_note_with_no_mile_on_an_unloaded_waypoint_is_covered_by_nobody(client, db_session):
    """An assignment is a range along the centerline. Treating "no mile" as
    covered would hand every maintainer a veto over every unplaced waypoint."""
    maintainer = _maintainer_of(db_session, 0, 2200)
    _note(db_session, maintainer.id, days_ago=2, mile=None)

    assert client.get("/disputes").json() == []


def test_a_loaded_mile_outranks_the_mile_typed_on_a_not_found(client, db_session):
    """Once the waypoint has a row, the typed mile stops mattering in both
    directions: a `not_found` claiming a mile inside the stretch, on a spring
    the export puts 600 miles away, is one hiker's note."""
    maintainer = _maintainer_of(db_session, 1400, 1410)
    _waypoint(db_session, 800)
    _note(db_session, maintainer.id, days_ago=2, mile=1405)

    assert client.get("/disputes").json() == []


def test_a_mile_typed_on_a_note_does_not_make_a_maintainer_cover_a_far_waypoint(client, db_session):
    """The reproduction from #1917 - A maintainer's note settles a water
    dispute anywhere on the trail, because the covering check reads the mile
    the note's author typed, not where the waypoint is. A maintainer of miles
    11.0 to 14.3, a spring at mile 1500 that two hikers could not find, and one
    "flowing" note from the maintainer about that spring claiming mile 12. The
    note's mile is what the author's client sent; the spring is where the
    export puts it."""
    club = Club(id=str(uuid.uuid4()), name="Local Club")
    db_session.add(club)
    maintainer = make_profile(db_session, Role.maintainer)
    db_session.add(
        MaintainerAssignment(
            id=str(uuid.uuid4()),
            maintainer_id=maintainer.id,
            club_id=club.id,
            start_mile=11.0,
            end_mile=14.3,
            effective_from=date(2020, 1, 1),
        )
    )
    db_session.commit()
    _waypoint(db_session, 1500.0)
    for hiker in (make_profile(db_session, Role.hiker), make_profile(db_session, Role.hiker)):
        _note(db_session, hiker.id, days_ago=3, mile=1500.0)
    _note(db_session, maintainer.id, days_ago=1, observation="flowing", mile=12.0)

    body = client.get("/disputes").json()

    assert [row["poi_id"] for row in body] == [_POI], "the far maintainer's note no longer clears it"
    assert body[0]["maintainer_said"] is False


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


def test_two_disputes_older_than_the_window_are_not_served(client, db_session):
    first = make_profile(db_session, Role.hiker)
    second = make_profile(db_session, Role.hiker)
    _note(db_session, first.id, days_ago=200)
    _note(db_session, second.id, days_ago=190)

    assert client.get("/disputes").json() == []


def test_a_live_dispute_still_stands_over_a_confirmation_older_than_the_window(client, db_session):
    """The 180-day bound in the query drops the 400-day-old confirmation, which
    could not have cleared a dispute made after it anyway (#1757)."""
    first = make_profile(db_session, Role.hiker)
    second = make_profile(db_session, Role.hiker)
    old_confirmer = make_profile(db_session, Role.hiker)
    _note(db_session, old_confirmer.id, days_ago=400, observation="found")
    _note(db_session, first.id, days_ago=10)
    _note(db_session, second.id, days_ago=2)

    assert [row["poi_id"] for row in client.get("/disputes").json()] == [_POI]


def test_the_disputes_query_bounds_observed_at_in_sql(client, db_session):
    """The window is in the WHERE clause, not only applied afterwards in Python
    (#1757), so the scan does not grow with every note ever written."""
    from sqlalchemy import event

    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        client.get("/disputes")
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    notes_query = [s for s in statements if "field_notes" in s and "observation IS NOT NULL" in s]
    assert notes_query, statements
    assert "observed_at >=" in notes_query[0]


def test_the_waypoint_mile_read_binds_no_parameter_per_waypoint(client, db_session):
    """An `IN` over the window's `poi_id`s binds one parameter each, and
    Postgres refuses past 65,535 - measured by the 2026-10-29 review, which
    turned `GET /disputes` into a 500 with 65,536 distinct ids. `poi_id` is
    free text and nothing throttles notes, so the read takes the whole table
    (one row per published waypoint) instead."""
    from sqlalchemy import event

    hikers = (make_profile(db_session, Role.hiker), make_profile(db_session, Role.hiker))
    for index in range(3):
        for hiker in hikers:
            _note(db_session, hiker.id, days_ago=1, poi_id=f"atc_water:{index}")

    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert len(client.get("/disputes").json()) == 3
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    waypoint_reads = [s for s in statements if "FROM waypoint_miles" in s]
    assert waypoint_reads, statements
    assert all(" IN " not in s.upper() for s in waypoint_reads), waypoint_reads
