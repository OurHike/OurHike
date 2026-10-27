"""The monthly close and the six-month delete (#1902, app/core/analytics_rollup.py).

Each test is one of the month-end snapshot problems the strategy page listed,
and what the rollup does about it: late arrivals, the delete outrunning the
close, plans split across clubs by their miles, distinct counts that do not
add, and a run that happens twice.
"""

import threading
import uuid
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.core import analytics_rollup
from app.core.analytics_rollup import ALL, add_months, closes_on, retention_start, run
from app.models.analytics import (
    AnalyticsAnomaly,
    AnalyticsEvent,
    AnalyticsIntake,
    AnalyticsMonth,
    AnalyticsMonthly,
    AnalyticsUser,
    IntakeOutcome,
    MonthStatus,
)

OCTOBER = date(2026, 10, 1)


def _event(db_session, day: date, *, received: date | None = None, **fields) -> AnalyticsEvent:
    event = AnalyticsEvent(
        id=str(uuid.uuid4()),
        local_date=day,
        received_on=received or day,
        event=fields.pop("event", "map_screen_viewed"),
        platform=fields.pop("platform", "android"),
        **fields,
    )
    db_session.add(event)
    db_session.commit()
    return event


def _value(db_session, month: date, metric: str, club: str = ALL, platform: str = ALL) -> float | None:
    row = db_session.get(AnalyticsMonthly, (month, metric, club, platform))
    return None if row is None else row.value


def _status(db_session, month: date) -> MonthStatus:
    return db_session.get(AnalyticsMonth, month).status


# --- what a month counts --------------------------------------------------------


def test_active_devices_come_from_the_phones_own_first_of_the_month_answer(db_session):
    """Three events from two phones that said "first this month" are two
    devices - counted with no identifier at all (EVENTING.md §2)."""
    _event(db_session, date(2026, 10, 3), month_first=True)
    _event(db_session, date(2026, 10, 4), month_first=False)
    _event(db_session, date(2026, 10, 9), month_first=True, ever_first=True)

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "devices_active") == 2
    assert _value(db_session, OCTOBER, "devices_new") == 1


def test_every_active_device_is_new_returning_or_back_again(db_session):
    """Growth accounting for every phone, from two answers each phone gives
    about itself - no identifier, and the three parts add up to the whole."""
    _event(db_session, date(2026, 10, 2), month_first=True, ever_first=True)  # new
    _event(db_session, date(2026, 10, 3), month_first=True, month_returning=True)  # here in September too
    _event(db_session, date(2026, 10, 4), month_first=True, month_returning=True)
    _event(db_session, date(2026, 10, 5), month_first=True)  # here before, but not in September
    _event(db_session, date(2026, 10, 6), month_returning=False)  # not a month_first row: counts nowhere

    run(db_session, today=date(2026, 10, 20))

    parts = [_value(db_session, OCTOBER, metric) for metric in ("devices_new", "devices_returning", "devices_back")]
    assert parts == [1, 2, 1]
    assert sum(parts) == _value(db_session, OCTOBER, "devices_active") == 4


def test_phones_that_did_each_thing_come_from_their_first_of_that_kind_this_month(db_session):
    """The funnel for every phone, not only for hikers who linked an account."""
    _event(db_session, date(2026, 10, 2), event="map_screen_viewed", kind_month_first=True, month_first=True)
    _event(db_session, date(2026, 10, 2), event="map_screen_viewed")
    _event(db_session, date(2026, 10, 3), event="hike_plan_made", kind_month_first=True, miles=4.0)
    _event(db_session, date(2026, 10, 9), event="hike_plan_made", miles=6.0)
    _event(db_session, date(2026, 10, 9), event="map_screen_viewed", kind_month_first=True, month_first=True)
    _event(db_session, date(2026, 10, 9), event="user_login", kind_month_first=True)

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "devices_map_view") == 2
    assert _value(db_session, OCTOBER, "devices_plan_made") == 1
    assert _value(db_session, OCTOBER, "plans_made") == 2, "events still count every plan"
    assert _value(db_session, OCTOBER, "devices_plan_completed") == 0
    assert _value(db_session, OCTOBER, "devices_login") == 1


def test_signed_in_phones_are_counted_by_their_first_row_of_the_month(db_session):
    _event(db_session, date(2026, 10, 2), month_first=True, signed_in=True)
    _event(db_session, date(2026, 10, 3), month_first=True, signed_in=False)
    _event(db_session, date(2026, 10, 4), month_first=False, signed_in=True)

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "devices_signed_in") == 1
    assert _value(db_session, OCTOBER, "devices_active") == 2


def test_hikers_who_said_yes_are_counted_once_however_many_events(db_session):
    for day in (3, 4, 5):
        _event(db_session, date(2026, 10, day), user_key="a" * 32)
    _event(db_session, date(2026, 10, 6), user_key="b" * 32)
    _event(db_session, date(2026, 10, 6))  # no key: a hiker who said no

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "hikers_active") == 2


def test_a_plan_is_split_across_clubs_by_its_miles_in_each(db_session):
    """ "Assigned by # miles specific for each club" (poll 2026-10-27): 20 of a
    30-mile plan's miles in one club make it two thirds of a plan there."""
    _event(db_session, date(2026, 10, 3), event="hike_plan_made", miles=30.0, clubs={"NYNJTC": 2 / 3, "AMC-DV": 1 / 3})

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "plans_made", club="NYNJTC") == pytest.approx(2 / 3)
    assert _value(db_session, OCTOBER, "plan_miles", club="NYNJTC") == pytest.approx(20.0)
    assert _value(db_session, OCTOBER, "plan_miles", club="AMC-DV") == pytest.approx(10.0)
    assert _value(db_session, OCTOBER, "plans_made") == 1, "across all clubs it is still one plan"


def test_club_shares_add_up_to_the_events_that_had_a_club(db_session):
    _event(db_session, date(2026, 10, 3), event="hike_plan_made", miles=9.0, clubs={"GATC": 0.5, "SMHC": 0.5})
    _event(db_session, date(2026, 10, 4), event="hike_plan_made", miles=4.0, clubs={"GATC": 1.0})

    run(db_session, today=date(2026, 10, 20))

    clubs = sum(_value(db_session, OCTOBER, "plans_made", club=club) for club in ("GATC", "SMHC"))
    assert clubs == pytest.approx(_value(db_session, OCTOBER, "plans_made"))


def test_devices_on_a_clubs_trails_come_from_the_phones_first_in_that_club(db_session):
    _event(db_session, date(2026, 10, 3), clubs={"PATC": 1.0}, club_firsts=["PATC"])
    _event(db_session, date(2026, 10, 4), clubs={"PATC": 1.0})
    _event(db_session, date(2026, 10, 5), clubs={"PATC": 1.0}, club_firsts=["PATC"])

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "devices_active", club="PATC") == 2
    assert _value(db_session, OCTOBER, "map_views", club="PATC") == 3


def test_each_platform_gets_its_own_slice_and_clubs_are_never_crossed_with_platforms(db_session):
    _event(db_session, date(2026, 10, 3), event="session", platform="ios", pageviews=4, clubs={"GMC": 1.0})
    _event(db_session, date(2026, 10, 3), event="session", platform="web", pageviews=6)

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "pageviews", platform="ios") == 4
    assert _value(db_session, OCTOBER, "pageviews", platform="web") == 6
    assert _value(db_session, OCTOBER, "pageviews") == 10
    crossed = db_session.query(AnalyticsMonthly).filter(AnalyticsMonthly.club != ALL, AnalyticsMonthly.platform != ALL).count()
    assert crossed == 0


def _hiker(key: str, *, first_seen_on: date, new_month: date, active_months: list[int]) -> AnalyticsUser:
    return AnalyticsUser(
        user_key=key * 32,
        first_seen_on=first_seen_on,
        new_month=new_month,
        last_seen_on=date(2026, 10, 2),
        first_platform="ios",
        last_platform="ios",
        active_months=active_months,
    )


def test_new_hikers_who_said_yes_are_counted_in_the_month_they_were_first_new(db_session):
    """By `new_month`, set once. Hiker c's first_seen_on moved into September
    when a second phone's late row arrived, and c is still October's new
    hiker - counted by first_seen_on, c was new in neither month."""
    db_session.add_all(
        [
            _hiker("a", first_seen_on=date(2026, 10, 2), new_month=OCTOBER, active_months=[202610]),
            _hiker("b", first_seen_on=date(2026, 9, 2), new_month=date(2026, 9, 1), active_months=[202609, 202610]),
            _hiker("c", first_seen_on=date(2026, 9, 20), new_month=OCTOBER, active_months=[202609, 202610]),
        ]
    )
    db_session.commit()
    _event(db_session, date(2026, 10, 2), user_key="a" * 32)

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "hikers_new") == 2


# --- provisional, then closed ---------------------------------------------------


def test_a_month_stays_provisional_until_its_close_date(db_session):
    _event(db_session, date(2026, 10, 3))

    run(db_session, today=closes_on(OCTOBER) - timedelta(days=1))

    assert _status(db_session, OCTOBER) == MonthStatus.provisional


def test_a_provisional_month_counts_a_late_arrival(db_session):
    """The phone that spent October's last week on a ridge, uploading in November."""
    _event(db_session, date(2026, 10, 3), month_first=True)
    run(db_session, today=date(2026, 11, 2))
    _event(db_session, date(2026, 10, 30), received=date(2026, 11, 5), month_first=True)

    run(db_session, today=date(2026, 11, 6))

    assert _value(db_session, OCTOBER, "devices_active") == 2


def test_a_closed_month_does_not_move_and_says_what_it_missed(db_session):
    _event(db_session, date(2026, 10, 3), month_first=True)
    run(db_session, today=closes_on(OCTOBER))
    assert _status(db_session, OCTOBER) == MonthStatus.closed
    _event(db_session, date(2026, 10, 30), received=date(2026, 11, 20), month_first=True)

    run(db_session, today=date(2026, 11, 21))

    assert _value(db_session, OCTOBER, "devices_active") == 1, "a published number does not move under a reader"
    assert _value(db_session, OCTOBER, "events_after_close") == 1


def test_a_row_arriving_on_the_close_day_after_the_run_is_counted_late(db_session):
    """The close is a run at 10:17 UTC and `received_on` is a date. Counting
    "received after the close day" missed every row that came in later that
    same day: in neither the frozen month nor the late count."""
    close_day = closes_on(OCTOBER)
    _event(db_session, date(2026, 10, 3), month_first=True)
    run(db_session, today=close_day, now=datetime.combine(close_day, time(10, 17)))
    _event(db_session, date(2026, 10, 30), received=close_day)  # that afternoon

    next_day = close_day + timedelta(days=1)
    run(db_session, today=next_day, now=datetime.combine(next_day, time(10, 17)))

    assert _value(db_session, OCTOBER, "events_after_close") == 1
    assert _value(db_session, OCTOBER, "events") == 1, "the frozen count did not move"


def test_a_run_that_missed_weeks_closes_every_month_that_is_due(db_session):
    _event(db_session, date(2026, 8, 3))
    _event(db_session, date(2026, 9, 3))

    run(db_session, today=date(2026, 11, 1))

    assert _status(db_session, date(2026, 8, 1)) == MonthStatus.closed
    assert _status(db_session, date(2026, 9, 1)) == MonthStatus.closed


def test_a_run_beside_another_cannot_close_a_month_the_other_closed(db_engine, db_session, monkeypatch):
    """Reproduced before the lock: a dispatch beside the schedule read October
    as open, the scheduled run closed it meanwhile, and the dispatch then
    recomputed October from a row that had arrived since and closed it again
    under a different number.

    `held` starts first and is held inside its first month's computation;
    `other` starts while it is held. With the lock, `other` waits at its first
    statement and then finds October closed. Without it, both close October.
    """
    _event(db_session, date(2026, 10, 3), month_first=True)
    _event(db_session, date(2026, 10, 4), month_first=True)
    close_day = closes_on(OCTOBER)
    sessions = sessionmaker(bind=db_engine)
    computing, release = threading.Event(), threading.Event()
    real_compute = analytics_rollup.compute_month
    held_thread: dict[str, threading.Thread] = {}

    def compute_held_once(db, month):
        if threading.current_thread() is held_thread["it"] and not computing.is_set():
            computing.set()
            release.wait(timeout=20)
        return real_compute(db, month)

    monkeypatch.setattr(analytics_rollup, "compute_month", compute_held_once)
    results: dict[str, analytics_rollup.RollupResult] = {}

    def a_run(name: str, at: time) -> None:
        with sessions() as db:
            results[name] = run(db, today=close_day, now=datetime.combine(close_day, at))

    held = threading.Thread(target=a_run, args=("held", time(10, 17)))
    held_thread["it"] = held
    held.start()
    assert computing.wait(timeout=20), "the first run never reached its computation"
    other = threading.Thread(target=a_run, args=("other", time(10, 18)))
    other.start()
    other.join(timeout=2)  # without the lock it finishes here; with it, it is waiting
    _event(db_session, date(2026, 10, 30), received=close_day, month_first=True)  # arrives meanwhile
    release.set()
    held.join(timeout=30)
    other.join(timeout=30)

    assert not held.is_alive() and not other.is_alive()
    assert [name for name in ("held", "other") if OCTOBER in results[name].closed] == ["held"]
    assert OCTOBER in results["other"].late_counted


def test_a_session_that_read_the_months_before_a_run_reads_them_again(db_engine, db_session):
    """The lock only helps if what is read after it is what is committed: a
    session holding October from before another run closed it must not act on
    its own copy."""
    _event(db_session, date(2026, 10, 3), month_first=True)
    run(db_session, today=date(2026, 10, 20))
    # Held, so the session's weak identity map keeps this copy rather than
    # letting it be collected and read afresh by accident.
    october = db_session.get(AnalyticsMonth, OCTOBER)
    assert october.status == MonthStatus.provisional
    with sessionmaker(bind=db_engine)() as elsewhere:
        run(elsewhere, today=closes_on(OCTOBER))

    result = run(db_session, today=closes_on(OCTOBER))

    assert OCTOBER not in result.closed and OCTOBER in result.late_counted


def test_running_twice_on_one_day_changes_nothing(db_session):
    _event(db_session, date(2026, 10, 3), event="hike_plan_made", miles=5.0, clubs={"GATC": 1.0}, month_first=True)
    run(db_session, today=date(2026, 10, 20))
    first = {(r.metric, r.club, r.platform): r.value for r in db_session.query(AnalyticsMonthly).all()}

    run(db_session, today=date(2026, 10, 20))

    second = {(r.metric, r.club, r.platform): r.value for r in db_session.query(AnalyticsMonthly).all()}
    assert first == second


# --- six months, and not one row longer ------------------------------------------


def test_a_closed_month_past_retention_loses_its_raw_rows_and_keeps_its_figures(db_session):
    april = date(2026, 4, 1)
    _event(db_session, date(2026, 4, 3), month_first=True)
    run(db_session, today=date(2026, 5, 20))  # closes April
    november_first = date(2026, 11, 1)
    assert retention_start(november_first) == date(2026, 5, 1)

    result = run(db_session, today=november_first)

    assert result.deleted == {april: 1}
    assert db_session.query(AnalyticsEvent).count() == 0
    assert _value(db_session, april, "devices_active") == 1
    assert db_session.get(AnalyticsMonth, april).raw_deleted_at is not None


def test_the_current_month_and_the_six_before_it_are_kept(db_session):
    _event(db_session, date(2026, 5, 3))
    _event(db_session, date(2026, 11, 3))

    run(db_session, today=date(2026, 11, 3))

    assert db_session.query(AnalyticsEvent).count() == 2


def test_intake_counts_and_findings_go_with_the_raw_rows(db_session):
    today = date(2027, 6, 15)
    cutoff = retention_start(today)
    for day in (cutoff - timedelta(days=1), cutoff):
        db_session.add(AnalyticsIntake(received_on=day, app_version="", outcome=IntakeOutcome.stored, rows=3))
        db_session.add(
            AnalyticsAnomaly(day=day, check_name="sessions", scope=ALL, status="low", first_seen_on=day, last_seen_on=day)
        )
    db_session.commit()

    run(db_session, today=today)

    counts = db_session.query(AnalyticsIntake).filter(AnalyticsIntake.outcome != IntakeOutcome.held).all()
    assert [row.received_on for row in counts] == [cutoff]
    assert [row.day for row in db_session.query(AnalyticsAnomaly).all()] == [cutoff]


def test_the_rollup_leaves_its_own_count_of_the_rows_held_after_its_deletes(db_session):
    """Rows held, for the storage ceiling, start from this count
    (app/core/analytics_storage.py): rows are deleted by the month they
    describe, while their `stored` counts are kept by the day they arrived."""
    for day in (date(2026, 4, 3), date(2026, 10, 3), date(2026, 10, 4)):
        _event(db_session, day, received=date(2026, 10, 5))

    run(db_session, today=date(2026, 11, 2))

    held = db_session.query(AnalyticsIntake).filter(AnalyticsIntake.outcome == IntakeOutcome.held).one()
    assert (held.received_on, held.rows) == (date(2026, 11, 2), 2), "April left retention; October's two stay"


def test_a_month_keeps_rows_for_its_most_named_clubs_and_no_others(db_session, monkeypatch):
    """A club id is any short word a phone sends, and each one a month named
    was twelve monthly rows kept for good: 25 requests of made-up clubs made
    720,000 of them (#1903's second review)."""
    monkeypatch.setattr(analytics_rollup, "MAX_CLUBS_PER_MONTH", 2)
    for club, times in (("GATC", 3), ("NOC", 2), ("MADEUP1", 1)):
        for _ in range(times):
            _event(db_session, date(2026, 10, 3), clubs={club: 1.0}, club_firsts=[club])

    run(db_session, today=date(2026, 10, 20))

    clubs = {row.club for row in db_session.query(AnalyticsMonthly).filter(AnalyticsMonthly.club != ALL)}
    assert clubs == {"GATC", "NOC"}


def test_a_month_that_never_closed_is_refused_deletion(db_session, monkeypatch):
    """The guard against the delete outrunning the close. `run` closes every
    due month first, so the only way to reach this is a close window longer
    than retention - which is the change it exists to catch."""
    monkeypatch.setattr(analytics_rollup, "CLOSE_AFTER_DAYS", 400)
    _event(db_session, date(2026, 4, 3))

    result = run(db_session, today=date(2026, 11, 1))

    assert result.refused == [date(2026, 4, 1)]
    assert db_session.query(AnalyticsEvent).count() == 1, "refused means nothing was deleted"


def test_a_night_with_no_rows_still_leaves_a_fresh_heartbeat(db_session):
    """POST /usage-events stops collecting when `computed_at` goes stale, so
    a run with nothing to count must still say it ran."""
    night = datetime(2026, 10, 20, 10, 17)

    result = run(db_session, today=night.date(), now=night)

    assert result.recomputed == [OCTOBER]
    state = db_session.get(AnalyticsMonth, OCTOBER)
    assert state.computed_at == night and state.status == MonthStatus.provisional


def test_the_current_month_is_recomputed_beside_a_closed_one(db_session):
    _event(db_session, date(2026, 10, 3))
    run(db_session, today=closes_on(OCTOBER))

    result = run(db_session, today=closes_on(OCTOBER) + timedelta(days=1))

    assert date(2026, 11, 1) in result.recomputed and OCTOBER not in result.recomputed


def test_every_month_records_the_definition_it_was_computed_under(db_session):
    _event(db_session, date(2026, 10, 3))

    run(db_session, today=date(2026, 10, 20), now=datetime(2026, 10, 20, 4, 0))

    state = db_session.get(AnalyticsMonth, OCTOBER)
    assert state.definition_version == analytics_rollup.DEFINITION_VERSION
    assert state.computed_at == datetime(2026, 10, 20, 4, 0)


def test_month_arithmetic_crosses_the_year(db_session):
    assert add_months(date(2026, 11, 1), 3) == date(2027, 2, 1)
    assert add_months(date(2027, 1, 1), -1) == date(2026, 12, 1)
    assert retention_start(date(2027, 2, 14)) == date(2026, 8, 1)
