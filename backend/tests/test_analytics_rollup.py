"""The monthly close and the six-month delete (#1902, app/core/analytics_rollup.py).

Each test is one of the month-end snapshot problems the strategy page listed,
and what the rollup does about it: late arrivals, the delete outrunning the
close, plans split across clubs by their miles, distinct counts that do not
add, and a run that happens twice.
"""

import uuid
from datetime import date, datetime, timedelta

import pytest

from app.core import analytics_rollup
from app.core.analytics_rollup import ALL, add_months, closes_on, retention_start, run
from app.models.analytics import AnalyticsEvent, AnalyticsMonth, AnalyticsMonthly, AnalyticsUser, MonthStatus

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


def test_new_hikers_who_said_yes_come_from_the_user_tables_first_seen(db_session):
    db_session.add_all(
        [
            AnalyticsUser(
                user_key="a" * 32,
                first_seen_on=date(2026, 10, 2),
                last_seen_on=date(2026, 10, 2),
                first_platform="ios",
                last_platform="ios",
                active_months=[202610],
            ),
            AnalyticsUser(
                user_key="b" * 32,
                first_seen_on=date(2026, 9, 2),
                last_seen_on=date(2026, 10, 2),
                first_platform="ios",
                last_platform="ios",
                active_months=[202609, 202610],
            ),
        ]
    )
    db_session.commit()
    _event(db_session, date(2026, 10, 2), user_key="a" * 32)

    run(db_session, today=date(2026, 10, 20))

    assert _value(db_session, OCTOBER, "hikers_new") == 1


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


def test_a_run_that_missed_weeks_closes_every_month_that_is_due(db_session):
    _event(db_session, date(2026, 8, 3))
    _event(db_session, date(2026, 9, 3))

    run(db_session, today=date(2026, 11, 1))

    assert _status(db_session, date(2026, 8, 1)) == MonthStatus.closed
    assert _status(db_session, date(2026, 9, 1)) == MonthStatus.closed


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


def test_a_month_that_never_closed_is_refused_deletion(db_session, monkeypatch):
    """The guard against the delete outrunning the close. `run` closes every
    due month first, so the only way to reach this is a close window longer
    than retention - which is the change it exists to catch."""
    monkeypatch.setattr(analytics_rollup, "CLOSE_AFTER_DAYS", 400)
    _event(db_session, date(2026, 4, 3))

    result = run(db_session, today=date(2026, 11, 1))

    assert result.refused == [date(2026, 4, 1)]
    assert db_session.query(AnalyticsEvent).count() == 1, "refused means nothing was deleted"


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
