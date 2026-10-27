"""The nightly data-quality checks (#1902, app/core/analytics_quality.py).

Each test is a way usage numbers go wrong in practice, and the check that has
to notice it - or, as often the point, NOT notice it: an alert that cries
wolf at low volume, or on every fresh day because offline phones have not
uploaded yet, is an alert nobody reads (CLAUDE.md, "Miss rather than cry wolf").
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.dialects.postgresql import insert

from app.core import analytics_quality as quality
from app.core.analytics_rollup import ALL, run
from app.models.analytics import (
    AnalyticsAnomaly,
    AnalyticsEvent,
    AnalyticsIntake,
    AnalyticsMonth,
    AnalyticsMonthly,
    IntakeOutcome,
    MonthStatus,
)

TODAY = date(2026, 11, 20)


def _rows(db_session, day: date, counts: dict[str, int], *, received: date | None = None, **fields) -> None:
    """`counts` rows of each event on `day`, in one insert."""
    values = []
    for event, n in counts.items():
        for _ in range(n):
            values.append(
                {
                    "id": str(uuid.uuid4()),
                    "local_date": day,
                    "received_on": received or day,
                    "event": event,
                    "platform": fields.get("platform", "android"),
                    "app_version": fields.get("app_version"),
                    "week_first": False,
                    "month_first": False,
                    "ever_first": False,
                    "kind_month_first": False,
                    "month_returning": False,
                    "signed_in": False,
                    "has_fix": False,
                    "seal": fields.get("seal", "none"),
                    "pageviews": 3 if event == "session" else None,
                    "session_length": "m1_to_5" if event == "session" else None,
                }
            )
    if values:
        db_session.execute(insert(AnalyticsEvent.__table__).values(values))
        db_session.commit()


def _steady(db_session, *, days: int = 63, sessions: int = 60, plans: int = 20, views: int = 40, until: date = TODAY):
    """A quiet, steady app for `days` days before `until`, all uploaded on the day."""
    for back in range(days, 0, -1):
        day = until - timedelta(days=back)
        _rows(db_session, day, {"session": sessions, "hike_plan_made": plans, "map_screen_viewed": views})


def _findings(db_session, check: str | None = None, scope: str = ALL):
    found = quality.run_checks(db_session, today=TODAY)
    return [f for f in found if (check is None or f.check_name == check) and f.scope == scope]


# --- the verdict -------------------------------------------------------------------


def test_too_little_history_is_learning_not_a_verdict():
    assert quality.judge(0, [30, 31, 29])[0] == "learning"


def test_too_few_events_to_judge_is_quiet_not_a_verdict():
    status, expected, _, _ = quality.judge(0, [3, 4, 2, 5, 3])

    assert status == "quiet" and expected == 3


def test_nothing_where_something_is_always_seen_is_zero():
    assert quality.judge(0, [40, 38, 45, 41, 39])[0] == "zero"


def test_a_three_percent_wobble_at_thousands_a_day_is_not_an_anomaly():
    """Statistically far out - and not worth anybody's morning."""
    assert quality.judge(9700, [10_000, 10_010, 9_990, 10_005, 9_995])[0] == "ok"


def test_a_halving_at_twenty_a_day_is_within_noise_and_not_an_anomaly():
    assert quality.judge(10, [20, 21, 19, 20, 22])[0] == "ok"


def test_a_collapse_at_hundreds_a_day_is_low_and_a_flood_is_high():
    history = [400, 410, 390, 405, 395]

    assert quality.judge(90, history)[0] == "low"
    assert quality.judge(1300, history)[0] == "high"


# --- the series ---------------------------------------------------------------------


def test_a_metric_that_stops_is_found(db_session):
    _steady(db_session, until=TODAY - timedelta(days=2))
    for back in (2, 1):
        _rows(db_session, TODAY - timedelta(days=back), {"session": 60, "map_screen_viewed": 40})

    days = {f.day for f in _findings(db_session, "plans_made") if f.status == "zero"}

    assert days == {TODAY - timedelta(days=2), TODAY - timedelta(days=1)}


def test_a_steady_app_raises_nothing(db_session):
    _steady(db_session)

    assert quality.run_checks(db_session, today=TODAY) == []


def test_a_fresh_day_short_of_its_late_uploads_is_not_low(db_session):
    """Yesterday always looks low before the offline phones find signal. Every
    day here gets 40% of its rows on the day and the rest five days later, so
    yesterday at one day old matches every earlier weekday at one day old."""
    for back in range(63, 0, -1):
        day = TODAY - timedelta(days=back)
        _rows(db_session, day, {"session": 40, "hike_plan_made": 16})
        late = day + timedelta(days=5)
        if late < TODAY:
            _rows(db_session, day, {"session": 60, "hike_plan_made": 24}, received=late)

    found = quality.run_checks(db_session, today=TODAY)

    assert [f for f in found if f.check_name in ("sessions", "plans_made")] == []


def test_a_plan_that_stopped_being_recorded_shows_per_session_while_traffic_climbs(db_session):
    """The season starts, sessions double, and the plain count of plans holds -
    because a release stopped recording most of them. Only the rate shows it."""
    _steady(db_session, until=TODAY - timedelta(days=3), sessions=100, plans=40, views=80)
    for back in (3, 2, 1):
        _rows(db_session, TODAY - timedelta(days=back), {"session": 200, "hike_plan_made": 8, "map_screen_viewed": 160})

    ratio = {f.day for f in _findings(db_session, "plans_made_per_session") if f.status == "low"}

    assert ratio == {TODAY - timedelta(days=back) for back in (3, 2, 1)}
    assert not [f for f in _findings(db_session, "map_views_per_session")]


def test_a_release_that_broke_one_event_is_named(db_session):
    for back in range(14, 0, -1):
        day = TODAY - timedelta(days=back)
        _rows(db_session, day, {"session": 40, "hike_plan_made": 12}, app_version="1.4.0")
        _rows(db_session, day, {"session": 30}, app_version="1.5.0")

    found = _findings(db_session, "plans_made_per_session", scope="version:1.5.0")

    assert [f.status for f in found] == ["low"]
    assert not _findings(db_session, "plans_made_per_session", scope="version:1.4.0")


# --- intake and the pipeline -----------------------------------------------------------


def test_refused_rows_from_one_release_are_found(db_session):
    yesterday = TODAY - timedelta(days=1)
    for version, outcome, rows in (
        ("1.4.0", IntakeOutcome.stored, 900),
        ("1.5.0", IntakeOutcome.stored, 100),
        ("1.5.0", IntakeOutcome.invalid, 60),
    ):
        db_session.add(AnalyticsIntake(received_on=yesterday, app_version=version, outcome=outcome, rows=rows))
    db_session.commit()

    assert [f.status for f in _findings(db_session, "rows_refused", scope="version:1.5.0")] == ["warn"]
    assert [f.status for f in _findings(db_session, "rows_refused")] == ["warn"]
    assert not _findings(db_session, "rows_refused", scope="version:1.4.0")


def test_rows_thrown_away_for_want_of_a_key_are_found(db_session):
    _rows(db_session, TODAY - timedelta(days=2), {"map_screen_viewed": 3}, seal="no_key")

    assert [f.status for f in _findings(db_session, "rows_unsealed_no_key")] == ["warn"]


def test_a_month_left_provisional_past_its_close_date_is_found(db_session):
    db_session.add(AnalyticsMonth(month=date(2026, 9, 1), status=MonthStatus.provisional, definition_version=1))
    db_session.commit()

    assert [f.day for f in _findings(db_session, "month_not_closed")] == [date(2026, 9, 1)]


# --- the sums that must hold ---------------------------------------------------------------


def test_the_rollups_own_figures_pass_every_invariant(db_session):
    october = date(2026, 10, 1)
    _rows(db_session, date(2026, 10, 3), {"session": 3, "hike_plan_made": 2})
    for fields in (
        {"month_first": True, "ever_first": True, "week_first": True},
        {"month_first": True, "month_returning": True},
        {"month_first": True},
    ):
        db_session.add(
            AnalyticsEvent(
                id=str(uuid.uuid4()),
                local_date=date(2026, 10, 5),
                received_on=date(2026, 10, 5),
                event="map_screen_viewed",
                platform="ios",
                **fields,
            )
        )
    db_session.commit()
    run(db_session, today=date(2026, 10, 20))

    assert db_session.get(AnalyticsMonthly, (october, "devices_active", ALL, ALL)).value == 3
    assert quality.invariant_findings(db_session) == []


def test_a_platform_that_does_not_add_up_is_broken(db_session):
    october = date(2026, 10, 1)
    for platform, value in ((ALL, 10.0), ("ios", 4.0), ("android", 5.0)):
        db_session.add(AnalyticsMonthly(month=october, metric="sessions", club=ALL, platform=platform, value=value))
    db_session.commit()

    names = {f.check_name for f in quality.invariant_findings(db_session) if f.status == "broken"}

    assert "platforms_add_up:sessions" in names


# --- what the table keeps ---------------------------------------------------------------------


def test_a_finding_keeps_the_night_it_first_appeared(db_session):
    finding = quality.Finding(TODAY - timedelta(days=1), "sessions", ALL, "low", 3, 60)
    quality.record(db_session, [finding], today=TODAY - timedelta(days=1))

    quality.record(db_session, [finding], today=TODAY)

    stored = db_session.get(AnalyticsAnomaly, (finding.day, "sessions", ALL))
    assert (stored.first_seen_on, stored.last_seen_on) == (TODAY - timedelta(days=1), TODAY)


def test_a_finding_tonight_no_longer_makes_is_resolved_and_an_old_one_is_history(db_session):
    recent = quality.Finding(TODAY - timedelta(days=2), "sessions", ALL, "low", 3, 60)
    old = quality.Finding(TODAY - timedelta(days=30), "plans_made", ALL, "zero", 0, 20)
    quality.record(db_session, [recent, old], today=TODAY - timedelta(days=1))

    quality.record(db_session, [], today=TODAY)

    assert db_session.get(AnalyticsAnomaly, (recent.day, "sessions", ALL)) is None, "late rows filled the gap"
    assert db_session.get(AnalyticsAnomaly, (old.day, "plans_made", ALL)) is not None


@pytest.mark.parametrize("check", ["platforms_add_up:sessions", "month_not_closed"])
def test_a_month_level_finding_that_no_longer_holds_is_resolved_whatever_its_month(db_session, check):
    quality.record(db_session, [quality.Finding(date(2026, 6, 1), check, ALL, "broken")], today=TODAY - timedelta(days=1))

    quality.record(db_session, [], today=TODAY)

    assert db_session.query(AnalyticsAnomaly).count() == 0
