"""The nightly data-quality checks (#1902, app/core/analytics_quality.py).

Each test is a way usage numbers go wrong in practice, and the check that has
to notice it - or, as often the point, NOT notice it: an alert that cries
wolf at low volume, or on every fresh day because offline phones have not
uploaded yet, is an alert nobody reads (CLAUDE.md, "Miss rather than cry wolf").
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.core import analytics_quality as quality
from app.core import analytics_storage
from app.core.analytics_rollup import ALL, run
from app.models.analytics import (
    AnalyticsAnomaly,
    AnalyticsEvent,
    AnalyticsIntake,
    AnalyticsMonth,
    AnalyticsMonthly,
    AnalyticsSealKey,
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
                    "week_first": fields.get("week_first", False),
                    "month_first": False,
                    "ever_first": False,
                    "kind_month_first": False,
                    "month_returning": False,
                    "signed_in": False,
                    "has_fix": False,
                    "seal": fields.get("seal", "none"),
                    "pageviews": fields.get("pageviews", 3) if event == "session" else None,
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


def test_an_outage_is_zero_even_where_a_dip_would_be_too_few_to_judge():
    """The demo seed's staged sign-in outage: about 8 expected, none seen.
    A dip from 8 to 5 is noise; a fall to nothing is not."""
    history = [8, 7, 13, 4, 14, 8, 14, 8]

    assert quality.judge(0, history)[0] == "zero"
    assert quality.judge(5, history)[0] == "quiet"


def test_a_zero_is_ordinary_where_more_than_a_quarter_of_the_same_weekdays_were_zero():
    """Two of five is what a metric that is simply rare looks like."""
    assert quality.judge(0, [8, 0, 9, 0, 10])[0] == "quiet"


def test_one_earlier_outage_on_the_same_weekday_does_not_switch_the_zero_rule_off():
    """With "never zero before", this returned ok: one outage in the history
    hid the next one for the eight weeks it stayed there."""
    assert quality.judge(0, [0, 12, 12, 13, 11, 12, 12, 12])[0] == "zero"


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


def test_a_season_that_triples_every_count_is_not_a_finding(db_session):
    """A rise in the plain count is the season far more often than a fault,
    and every rate per session here holds."""
    _steady(db_session, until=TODAY - timedelta(days=3))
    for back in (3, 2, 1):
        _rows(db_session, TODAY - timedelta(days=back), {"session": 180, "hike_plan_made": 60, "map_screen_viewed": 120})

    assert quality.run_checks(db_session, today=TODAY) == []


def test_a_rate_per_session_that_triples_is_still_high(db_session):
    """Ratio checks keep both directions: a release recording each plan
    three times is a fault, and only the rate can tell it from a busy day."""
    _steady(db_session, until=TODAY - timedelta(days=3))
    for back in (3, 2, 1):
        _rows(db_session, TODAY - timedelta(days=back), {"session": 60, "hike_plan_made": 60, "map_screen_viewed": 40})

    assert {f.status for f in _findings(db_session, "plans_made_per_session")} == {"high"}
    assert _findings(db_session, "plans_made") == [], "the plain count's rise is not a finding"


def test_screens_falling_are_found_per_session_and_not_as_a_count_of_their_own(db_session):
    _steady(db_session, until=TODAY - timedelta(days=3))
    for back in (3, 2, 1):
        _rows(
            db_session, TODAY - timedelta(days=back), {"session": 60, "hike_plan_made": 20, "map_screen_viewed": 40}, pageviews=1
        )

    assert _findings(db_session, "pageviews") == []
    assert {f.status for f in _findings(db_session, "pageviews_per_session")} == {"low"}


def test_a_platform_that_goes_silent_is_found_while_the_total_still_looks_ordinary(db_session):
    """Half the app's sessions gone is inside the whole app's band; all of
    one platform's is not."""
    for back in range(63, 0, -1):
        day = TODAY - timedelta(days=back)
        _rows(db_session, day, {"session": 30}, platform="ios", week_first=True)
        if back > 2:
            _rows(db_session, day, {"session": 30}, platform="android", week_first=True)

    android = {(f.check_name, f.day, f.status) for f in _findings(db_session, scope="platform:android")}

    silent_days = {TODAY - timedelta(days=2), TODAY - timedelta(days=1)}
    assert android == {(metric, day, "zero") for metric in ("sessions", "phones_this_week") for day in silent_days}
    assert _findings(db_session, "sessions") == [], "the whole app's sessions stayed inside their band"


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


def test_a_version_called_unknown_and_rows_with_no_version_are_two_findings(db_session):
    """Reproduced: both came out as `version:unknown`, two findings with one
    key, and Postgres refused the night's whole insert."""
    yesterday = TODAY - timedelta(days=1)
    for version in ("", "unknown"):
        for outcome, rows in ((IntakeOutcome.stored, 100), (IntakeOutcome.invalid, 20)):
            db_session.add(AnalyticsIntake(received_on=yesterday, app_version=version, outcome=outcome, rows=rows))
    db_session.commit()

    quality.record(db_session, quality.run_checks(db_session, today=TODAY), today=TODAY)

    scopes = {row.scope for row in db_session.query(AnalyticsAnomaly).filter(AnalyticsAnomaly.check_name == "rows_refused")}
    assert scopes == {ALL, "version:(none)", "version:unknown"}


def test_batches_turned_away_whole_are_found(db_session):
    yesterday = TODAY - timedelta(days=1)
    db_session.add(AnalyticsIntake(received_on=yesterday, app_version="", outcome=IntakeOutcome.over_budget, rows=5))
    db_session.add(AnalyticsIntake(received_on=yesterday, app_version="", outcome=IntakeOutcome.paused, rows=3))
    db_session.commit()

    found = {(f.check_name, f.status) for f in _findings(db_session)}

    assert {("rows_over_budget", "warn"), ("rows_paused", "warn")} <= found


@pytest.mark.parametrize(("held", "warned"), [(7, False), (8, True)], ids=["seven-tenths", "eight-tenths"])
def test_rows_held_near_the_storage_ceiling_are_a_warning_before_a_batch_is_turned_away(db_session, monkeypatch, held, warned):
    """The maintainer keeps six months of rows and moves to a paid plan before
    the ceiling binds (poll, 2026-10-27): this is the notice to move."""
    monkeypatch.setattr(settings, "analytics_storage_ceiling_mb", 1)
    monkeypatch.setattr(analytics_storage, "STORED_ROW_BYTES", 1024 * 1024 // 10)
    db_session.add(
        AnalyticsIntake(received_on=TODAY - timedelta(days=30), app_version="1.4.0", outcome=IntakeOutcome.stored, rows=held)
    )
    db_session.commit()

    found = quality.run_checks(db_session, today=TODAY)

    assert (quality.Finding(TODAY, "storage_near_ceiling", ALL, "warn", held / 10, 0.8) in found) is warned


@pytest.mark.parametrize(("tenths", "warned"), [(7, False), (8, True)], ids=["seven-tenths", "eight-tenths"])
def test_usage_tables_on_disk_near_the_storage_ceiling_are_a_warning_while_few_rows_are_held(
    db_session, monkeypatch, tenths, warned
):
    """A table's file keeps the room of the rows deleted from it, and real rows
    can run larger than the measured 382 bytes: either way the plan holds the
    room, and rows held alone would not say so."""
    monkeypatch.setattr(settings, "analytics_storage_ceiling_mb", 10)
    monkeypatch.setattr(analytics_storage, "usage_tables_bytes", lambda db: tenths * 1024 * 1024)

    found = quality.run_checks(db_session, today=TODAY)

    assert (quality.Finding(TODAY, "storage_near_ceiling", ALL, "warn", tenths / 10, 0.8) in found) is warned


@pytest.mark.parametrize(("tenths", "warned"), [(7, False), (8, True)], ids=["seven-tenths", "eight-tenths"])
def test_a_database_near_its_plans_quota_is_a_warning_before_it_stops_taking_writes(db_session, monkeypatch, tenths, warned):
    """Supabase turns a Free-plan database read-only past 500 MB - every
    write the app makes, not only usage rows."""
    monkeypatch.setattr(settings, "database_quota_mb", 10)
    monkeypatch.setattr(analytics_storage, "database_bytes", lambda db: tenths * 1024 * 1024)

    found = quality.run_checks(db_session, today=TODAY)

    assert (quality.Finding(TODAY, "database_near_quota", ALL, "warn", tenths / 10, 0.8) in found) is warned


@pytest.mark.parametrize(
    ("through", "warned"), [(date(2027, 1, 1), True), (date(2027, 2, 1), False)], ids=["two-months-ahead", "three"]
)
def test_sealing_keys_published_less_than_three_months_ahead_are_a_warning(db_session, through, warned):
    """Past the last month with a key, every fix and account is thrown away
    (scripts/analytics_keys.py). The report's data-health line used to work
    this out in the page, where only somebody opening the file would see it."""
    db_session.add(AnalyticsSealKey(month=through, public_key=bytes(32)))
    db_session.commit()

    found = {(f.check_name, f.observed) for f in quality.run_checks(db_session, today=TODAY)}

    assert (("seal_keys_running_out", 2.0) in found) is warned


def test_no_sealing_keys_at_all_is_left_to_the_rows_it_costs(db_session):
    """An environment collecting nothing yet loses nothing; one collecting
    with no key raises `rows_unsealed_no_key` for the rows thrown away."""
    found = {f.check_name for f in quality.run_checks(db_session, today=TODAY)}

    assert "seal_keys_running_out" not in found


def test_a_rollup_that_failed_tonight_is_a_finding_tonight(db_session):
    found = quality.run_checks(db_session, today=TODAY, rollup_failed=True)

    assert quality.Finding(TODAY, "rollup_failed", ALL, "warn") in found


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


def _closed_month_with_late_rows(db_session, month: date, closed_at: datetime) -> None:
    """A closed month whose late rows are 10% of what it froze with - five times LATE_SHARE."""
    db_session.add(AnalyticsMonth(month=month, status=MonthStatus.closed, definition_version=1, closed_at=closed_at))
    for metric, value in (("events", 100.0), ("events_after_close", 10.0)):
        db_session.add(AnalyticsMonthly(month=month, metric=metric, club=ALL, platform=ALL, value=value))
    db_session.commit()


def test_a_month_frozen_more_than_a_fortnight_is_not_judged_again(db_session):
    """Reproduced: eight months of the simulation left three
    late_rows_after_close warnings re-made every night, for ever, so the
    tracking issue could never close."""
    september, october = date(2026, 9, 1), date(2026, 10, 1)
    _closed_month_with_late_rows(db_session, september, datetime(2026, 10, 15, 10, 17))  # 36 days before TODAY
    _closed_month_with_late_rows(db_session, october, datetime(2026, 11, 15, 10, 17))  # 5 days before TODAY

    late = [f.day for f in _findings(db_session, "late_rows_after_close")]

    assert late == [october]


def test_a_frozen_months_last_finding_is_kept_as_history(db_session):
    september = date(2026, 9, 1)
    _closed_month_with_late_rows(db_session, september, datetime(2026, 10, 15, 10, 17))
    old = quality.Finding(september, "late_rows_after_close", ALL, "warn", 0.1, quality.LATE_SHARE)
    quality.record(db_session, [old], today=date(2026, 10, 20))

    quality.record(db_session, quality.run_checks(db_session, today=TODAY), today=TODAY)

    kept = db_session.get(AnalyticsAnomaly, (september, "late_rows_after_close", ALL))
    assert kept is not None and kept.last_seen_on == date(2026, 10, 20)


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


def test_two_findings_with_one_key_are_stored_once_as_the_more_severe(db_session):
    day = TODAY - timedelta(days=1)
    pair = [quality.Finding(day, "sessions", ALL, "low", 20, 60), quality.Finding(day, "sessions", ALL, "zero", 0, 60)]

    quality.record(db_session, pair, today=TODAY)

    assert db_session.get(AnalyticsAnomaly, (day, "sessions", ALL)).status == "zero"


# --- what the public issue hears -------------------------------------------------------


def test_a_statistical_finding_reaches_the_public_on_its_second_night(db_session):
    low = quality.Finding(TODAY - timedelta(days=2), "sessions", ALL, "low", 20, 60)
    first = quality.record(db_session, [low], today=TODAY - timedelta(days=1))
    assert quality.public_findings(db_session, first, today=TODAY - timedelta(days=1)) == []

    second = quality.record(db_session, [low], today=TODAY)

    assert quality.public_findings(db_session, second, today=TODAY) == [low]


def test_a_sum_that_does_not_add_up_reaches_the_public_at_once(db_session):
    broken = quality.Finding(date(2026, 10, 1), "session_lengths_add_up", ALL, "broken", 9, 10)

    tonight = quality.record(db_session, [broken], today=TODAY)

    assert quality.public_findings(db_session, tonight, today=TODAY) == [broken]
