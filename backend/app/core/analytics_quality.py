"""Data quality for usage measurement: anomalies in each metric, and the sums that must hold (#1902).

Run every night after the rollup by .github/workflows/analytics-rollup.yml
(`scripts/analytics_quality.py`). Findings go into `analytics_anomalies`;
a check that comes out normal writes nothing. The usage report's data-quality
panel draws from here (app/core/analytics_report.py), and production's run
opens, updates or closes one tracking issue - which, the repository being
public, names checks and never figures.

WHAT IS CHECKED, AND WHY EACH ONE

1. **Each metric, each day, against the same weekday in the weeks before.**
   Installs, sign-ins, plans made and completed, map views, sessions, and
   phones counted for the first time that week - and sessions and phones per
   platform, so a whole platform going silent is seen even while the other
   two carry the total. Same weekday because hiking is a weekend activity and
   a Saturday is not a Tuesday; the median of up to `HISTORY_WEEKS` of them,
   so one odd week cannot drag the baseline. **Only a fall is a finding**
   (`low` or `zero`), because a rise is the season far more often than a
   fault: on synthetic Poisson counts climbing 6% a week, `judge` called one
   series at 20 a day high on 7 of 154 nights (measured 2026-10-27), and a
   night judges seven days of seven series; the review that took `high` out
   counted it on 51% of nights. Screens are not in this list: a sum of
   per-session counts swings far more than a count of events, and
   `pageviews_per_session` below already catches the instrumentation breaking.
2. **Compared lag for lag.** This app is offline-first: yesterday's count is
   missing everything still on a ridge. Each day is compared with earlier
   days *as they stood at the same age* - rows received within the same number
   of whole days of their date - which `received_on` makes exact. Whole days:
   the job runs mid-morning, so today's arrivals are partial and are left out
   on both sides. Without this, every fresh day reads low, every night, and
   the check is noise.
3. **Each event per session**, both directions. A release that stops
   recording plans shows up here as plans-per-session collapsing, even in a
   month when traffic is climbing for the season and the plain count looks
   fine; one that records each plan twice shows as the rate doubling.
4. **Each release against the others.** The same per-session rates, for one
   app version over a fortnight against every other version: the shape of a
   release that broke one event and nothing else.
5. **Intake.** Rows the server refused, by version (`analytics_intake`) -
   the only trace a refused row leaves - resends, and batches turned away
   because the day's budget ran out or the rollup had stopped.
6. **The pipeline.** Rows thrown away for want of a published key, a month
   left provisional past its close date (the rollup is not running), closed
   months still collecting rows (`CLOSE_AFTER_DAYS` is too short), and a
   night the rollup itself failed (`scripts/analytics_quality.py
   --rollup-outcome`).
7. **The sums that must hold**, on every month still open or closed within
   `MONTH_JUDGED_DAYS`: platforms add up to the total, new + returning +
   back-again add up to the active phones, session lengths add up to
   sessions, no club has more phones than the whole app. A failure there is a
   bug or a lying client, not noise. A month frozen longer than that is not
   judged again - its figures cannot change, so re-making its finding every
   night would only keep the tracking issue open for ever.

MISS RATHER THAN CRY WOLF

CLAUDE.md's rule for anything alert-shaped, and the reason every threshold
below asks for TWO things: an anomaly must be `Z` deviations out AND at least
`RELATIVE` away from what was expected. At a few events a day the first
alone fires on noise; at thousands, the second alone fires on a 3% wobble.
Too little history says `learning`, too few events says `quiet` - honest
non-answers rather than guesses. And the public tracking issue hears of a
statistical finding only on its second night (`public_findings`), while a
sum that does not add up goes there at once. All of these numbers are
@unvalidated: picked, not measured, and what would settle them is a quarter
of real data and the maintainer's judgement of which findings were worth
reading.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.analytics_rollup import ALL, add_months, closes_on, retention_start
from app.models.analytics import AnalyticsAnomaly, AnalyticsMonth, AnalyticsMonthly, MonthStatus, UsagePlatform

# @unvalidated - see the module docstring for what would settle each.
Z = 4.0
RELATIVE = 0.5
MIN_EXPECTED = 10.0
# Nothing at all is judged on its own terms, because it is far stronger
# evidence than a dip: with 7 expected, a Poisson count is zero about 0.09% of
# the time (e^-7), and an outage is exactly a metric falling to nothing. So a
# zero is called below MIN_EXPECTED - but not where more than a quarter of the
# same weekdays were zero too, which is what a metric that is simply rare
# looks like. A quarter rather than "never": with "never", one earlier outage
# on that weekday switched the rule off for the eight weeks it stayed in the
# history. Reasoned from the Poisson tail, not measured; the staged sign-in
# outage in the demo seed (two days at ~8 expected) is what it was checked
# against.
ZERO_MIN_EXPECTED = 7.0
ZERO_HISTORY_SHARE = 0.25
HISTORY_WEEKS = 8
MIN_HISTORY = 4
EVALUATE_DAYS = 7
SERIES_DAYS = 56
MIN_SESSIONS_FOR_RATIO = 50
VERSION_WINDOW_DAYS = 14
MIN_VERSION_SESSIONS = 200
VERSION_FLOOR = 0.2
REFUSED_SHARE = 0.01
REFUSED_SHARE_VERSION = 0.05
MIN_REFUSED_ROWS = 10
DUPLICATE_SHARE = 0.2
MIN_INTAKE_ROWS = 100
LATE_SHARE = 0.02
OVERDUE_GRACE_DAYS = 2
# How long after its close a month's sums are still judged. A fortnight, the
# same span CLOSE_AFTER_DAYS gives late rows before the close; after it, the
# month's figures are frozen and its late count is history. @unvalidated, like
# the rest: what would settle it is how long after a close the maintainer
# still acts on a finding about that month.
MONTH_JUDGED_DAYS = 14

# Every daily series, by name. Each is a column of `_DAILY` below. Screens
# (`pageviews`) are loaded for `pageviews_per_session` and drawn by nothing
# else.
DAILY_METRICS = (
    "installs",
    "logins",
    "plans_made",
    "plans_completed",
    "map_views",
    "sessions",
    "pageviews",
    "phones_this_week",
)

# The series judged on their own count - every daily series but screens (the
# module docstring says why), and the panel the report draws.
VOLUME_METRICS = tuple(metric for metric in DAILY_METRICS if metric != "pageviews")

# The same, for each platform alone: enough to see one go silent.
PLATFORM_METRICS = ("sessions", "phones_this_week")
PLATFORMS = tuple(platform.value for platform in UsagePlatform)

# Events checked per session, for instrumentation that broke quietly.
PER_SESSION = ("logins", "plans_made", "plans_completed", "map_views", "pageviews")

# A volume finding is a fall. A ratio finding may go either way.
FALLS = ("low", "zero")
EITHER_WAY = ("low", "high", "zero")

# Judged against a noisy expectation, so the public issue waits for a second
# night before it hears of one. `broken` and `warn` are not estimates.
STATISTICAL = frozenset(EITHER_WAY)

# What the intake check calls a row that carried no readable version. Not
# "unknown", which a version string could be: two findings would share one
# key, and `record` would refuse the night's whole insert.
NO_VERSION = "(none)"

_DAILY = text(
    """
    select local_date, received_on,
      count(*) filter (where event = 'app_installed') as installs,
      count(*) filter (where event = 'user_login') as logins,
      count(*) filter (where event = 'hike_plan_made') as plans_made,
      count(*) filter (where event = 'hike_plan_completed') as plans_completed,
      count(*) filter (where event = 'map_screen_viewed') as map_views,
      count(*) filter (where event = 'session') as sessions,
      coalesce(sum(pageviews) filter (where event = 'session'), 0) as pageviews,
      count(*) filter (where week_first) as phones_this_week
    from analytics_events
    where local_date >= :start and local_date <= :end
    group by local_date, received_on
    """
)

_DAILY_BY_PLATFORM = text(
    """
    select platform, local_date, received_on,
      count(*) filter (where event = 'session') as sessions,
      count(*) filter (where week_first) as phones_this_week
    from analytics_events
    where local_date >= :start and local_date <= :end
    group by platform, local_date, received_on
    """
)

_BY_VERSION = text(
    """
    select coalesce(app_version, '') as version,
      count(*) filter (where event = 'session') as sessions,
      count(*) filter (where event = 'user_login') as logins,
      count(*) filter (where event = 'hike_plan_made') as plans_made,
      count(*) filter (where event = 'hike_plan_completed') as plans_completed,
      count(*) filter (where event = 'map_screen_viewed') as map_views,
      coalesce(sum(pageviews) filter (where event = 'session'), 0) as pageviews
    from analytics_events
    where local_date >= :start and local_date <= :end
    group by 1
    """
)

_INTAKE = text(
    """
    select received_on, app_version, outcome, rows from analytics_intake
    where received_on >= :start and received_on <= :end
    """
)

_NO_KEY = text("select count(*) from analytics_events where seal = 'no_key' and received_on >= :start")


@dataclass(frozen=True)
class Finding:
    day: date
    check_name: str
    scope: str
    status: str
    observed: float | None = None
    expected: float | None = None
    low: float | None = None
    high: float | None = None

    @property
    def key(self) -> tuple[date, str, str]:
        """The row it is stored as - `analytics_anomalies`' primary key, at the columns' widths."""
        return (self.day, self.check_name[:48], self.scope[:64])


@dataclass(frozen=True)
class Judgement:
    """One metric on one day: what was seen, what was expected, and the verdict."""

    day: date
    observed: float
    expected: float | None
    low: float | None
    high: float | None
    status: str  # ok, low, high, zero, quiet, learning


def judge(observed: float, history: list[float], *, scale: float = 1.0) -> tuple[str, float | None, float, float]:
    """The verdict on one observation against its history.

    `history` holds comparable past values (same weekday, same age); `scale`
    turns a rate into a count when `history` holds rates. Returns the status,
    the expected value, and the band outside which - by both tests - a value
    would have been called an anomaly.
    """
    if len(history) < MIN_HISTORY:
        return "learning", None, 0.0, 0.0
    centre = statistics.median(history)
    expected = centre * scale
    spread = 1.4826 * statistics.median(abs(value - centre) for value in history) * scale
    deviation = max(math.sqrt(max(expected, 1.0)), spread)
    low = max(0.0, min(expected - Z * deviation, expected * (1 - RELATIVE)))
    high = max(expected + Z * deviation, expected * (1 + RELATIVE))
    zeros = sum(1 for value in history if value == 0)
    if observed == 0 and expected >= ZERO_MIN_EXPECTED and zeros <= ZERO_HISTORY_SHARE * len(history):
        return "zero", expected, low, high
    if expected < MIN_EXPECTED:
        return "quiet", expected, low, high
    if observed < low:
        return "low", expected, low, high
    if observed > high:
        return "high", expected, low, high
    return "ok", expected, low, high


class Arrivals:
    """Daily counts, kept by the day rows arrived so any day can be read at any age."""

    def __init__(self, rows, metrics: tuple[str, ...] = DAILY_METRICS) -> None:
        self._by: dict[str, dict[date, list[tuple[date, float]]]] = {metric: defaultdict(list) for metric in metrics}
        self.first_day: date | None = None
        for row in rows:
            day, received = row["local_date"], row["received_on"]
            self.first_day = day if self.first_day is None else min(self.first_day, day)
            for metric in metrics:
                if row[metric]:
                    self._by[metric][day].append((received, float(row[metric])))

    def at(self, metric: str, day: date, age: int) -> float:
        """The count for `day` as it stood `age` days after it."""
        cutoff = day + timedelta(days=age)
        return sum(count for received, count in self._by[metric].get(day, ()) if received <= cutoff)

    def history(self, metric: str, day: date, age: int) -> list[float]:
        """The same weekday in up to HISTORY_WEEKS weeks before, each at the same age."""
        days = [day - timedelta(weeks=week) for week in range(1, HISTORY_WEEKS + 1)]
        return [self.at(metric, past, age) for past in days if self.first_day is not None and past >= self.first_day]


def _series_window(today: date) -> dict[str, date]:
    return {"start": max(retention_start(today), today - timedelta(days=SERIES_DAYS + HISTORY_WEEKS * 7)), "end": today}


def load_arrivals(db: Session, today: date) -> Arrivals:
    return Arrivals(db.execute(_DAILY, _series_window(today)).mappings())


def load_platform_arrivals(db: Session, today: date) -> dict[str, Arrivals]:
    """`PLATFORM_METRICS` for each platform alone. A platform never seen has no history, so it is `learning`."""
    rows: dict[str, list] = defaultdict(list)
    for row in db.execute(_DAILY_BY_PLATFORM, _series_window(today)).mappings():
        rows[row["platform"]].append(row)
    return {platform: Arrivals(rows[platform], PLATFORM_METRICS) for platform in PLATFORMS}


def completed_age(today: date, day: date) -> int:
    """Whole days of arrivals `day` has had by tonight: today's are still coming."""
    return (today - day).days - 1


def daily_judgements(arrivals: Arrivals, metric: str, today: date, days: int) -> list[Judgement]:
    """`metric` for each of the `days` days before today, each judged at its age now."""
    out = []
    for back in range(days, 0, -1):
        day = today - timedelta(days=back)
        age = completed_age(today, day)
        observed = arrivals.at(metric, day, age)
        status, expected, low, high = judge(observed, arrivals.history(metric, day, age))
        out.append(
            Judgement(
                day, observed, expected, low if expected is not None else None, high if expected is not None else None, status
            )
        )
    return out


def _volume_findings(
    arrivals: Arrivals, today: date, *, metrics: tuple[str, ...] = VOLUME_METRICS, scope: str = ALL
) -> list[Finding]:
    findings = []
    for metric in metrics:
        for item in daily_judgements(arrivals, metric, today, EVALUATE_DAYS):
            if item.status in FALLS:
                findings.append(Finding(item.day, metric, scope, item.status, item.observed, item.expected, item.low, item.high))
    return findings


def _platform_findings(platforms: dict[str, Arrivals], today: date) -> list[Finding]:
    return [
        finding
        for platform, arrivals in sorted(platforms.items())
        for finding in _volume_findings(arrivals, today, metrics=PLATFORM_METRICS, scope=f"platform:{platform}")
    ]


def _ratio_findings(arrivals: Arrivals, today: date) -> list[Finding]:
    findings = []
    for back in range(EVALUATE_DAYS, 0, -1):
        day = today - timedelta(days=back)
        age = completed_age(today, day)
        sessions = arrivals.at("sessions", day, age)
        if sessions < MIN_SESSIONS_FOR_RATIO:
            continue
        past_sessions = arrivals.history("sessions", day, age)
        for metric in PER_SESSION:
            past = arrivals.history(metric, day, age)
            rates = [count / base for count, base in zip(past, past_sessions, strict=True) if base > 0]
            observed = arrivals.at(metric, day, age)
            status, expected, low, high = judge(observed, rates, scale=sessions)
            if status in EITHER_WAY:
                findings.append(Finding(day, f"{metric}_per_session", ALL, status, observed, expected, low, high))
    return findings


def _version_findings(db: Session, today: date) -> list[Finding]:
    """A release whose rate of some event collapsed against every other release."""
    window = {"start": today - timedelta(days=VERSION_WINDOW_DAYS), "end": today - timedelta(days=1)}
    rows = [dict(row) for row in db.execute(_BY_VERSION, window).mappings()]
    if len(rows) < 2:
        return []
    totals = {key: sum(float(row[key]) for row in rows) for key in ("sessions", *PER_SESSION)}
    day = today - timedelta(days=1)
    findings = []
    for row in rows:
        sessions = float(row["sessions"])
        other_sessions = totals["sessions"] - sessions
        if sessions < MIN_VERSION_SESSIONS or other_sessions < MIN_VERSION_SESSIONS or not row["version"]:
            continue
        for metric in PER_SESSION:
            rate = (totals[metric] - float(row[metric])) / other_sessions
            expected = rate * sessions
            observed = float(row[metric])
            if expected >= 2 * MIN_EXPECTED and observed <= expected * VERSION_FLOOR:
                findings.append(Finding(day, f"{metric}_per_session", f"version:{row['version']}", "low", observed, expected))
    return findings


# Batches turned away whole by POST /usage-events (app/routers/analytics.py).
# Any at all is worth a look: either real traffic outgrew the budget, or the
# rollup stopped and collection paused behind it.
_TURNED_AWAY = (("over_budget", "rows_over_budget"), ("paused", "rows_paused"))


def _intake_findings(db: Session, today: date) -> list[Finding]:
    rows = db.execute(_INTAKE, {"start": today - timedelta(days=EVALUATE_DAYS), "end": today - timedelta(days=1)})
    days: dict[date, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for received_on, version, outcome, count in rows:
        outcome = getattr(outcome, "value", outcome)
        days[received_on][version][outcome] += count
        days[received_on]["*"][outcome] += count
    refused = ("invalid", "too_old", "future")
    findings = []
    for day, versions in sorted(days.items()):
        for version, outcomes in versions.items():
            bad = sum(outcomes[name] for name in refused)
            total = bad + outcomes["stored"] + outcomes["duplicate"]
            limit = REFUSED_SHARE if version == "*" else REFUSED_SHARE_VERSION
            scope = ALL if version == "*" else f"version:{version or NO_VERSION}"
            if bad >= MIN_REFUSED_ROWS and total and bad / total >= limit:
                findings.append(Finding(day, "rows_refused", scope, "warn", bad / total, limit))
            accepted = outcomes["stored"] + outcomes["duplicate"]
            if version == "*" and accepted >= MIN_INTAKE_ROWS and outcomes["duplicate"] / accepted >= DUPLICATE_SHARE:
                findings.append(Finding(day, "rows_resent", ALL, "warn", outcomes["duplicate"] / accepted, DUPLICATE_SHARE))
        for outcome, check in _TURNED_AWAY:
            if versions["*"][outcome]:
                findings.append(Finding(day, check, ALL, "warn", float(versions["*"][outcome])))
    return findings


def _pipeline_findings(db: Session, today: date) -> list[Finding]:
    findings = []
    unsealed = db.execute(_NO_KEY, {"start": today - timedelta(days=EVALUATE_DAYS)}).scalar_one()
    if unsealed:
        findings.append(Finding(today - timedelta(days=1), "rows_unsealed_no_key", ALL, "warn", float(unsealed)))
    for state in db.query(AnalyticsMonth).all():
        status = getattr(state.status, "value", state.status)
        if status == MonthStatus.provisional.value and today > closes_on(state.month) + timedelta(days=OVERDUE_GRACE_DAYS):
            findings.append(Finding(state.month, "month_not_closed", ALL, "warn"))
    return findings


def frozen_months(db: Session, today: date) -> set[date]:
    """Months closed more than `MONTH_JUDGED_DAYS` ago: their sums are judged no more.

    A month with no `analytics_months` row is not frozen - nothing says it
    closed - so a figure written by hand is still checked.
    """
    cutoff = today - timedelta(days=MONTH_JUDGED_DAYS)
    return {
        state.month
        for state in db.query(AnalyticsMonth).filter(AnalyticsMonth.closed_at.isnot(None)).all()
        if getattr(state.status, "value", state.status) == MonthStatus.closed.value and state.closed_at.date() < cutoff
    }


def _cells(db: Session) -> dict[date, dict[tuple[str, str], dict[str, float]]]:
    by_month: dict[date, dict[tuple[str, str], dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for row in db.query(AnalyticsMonthly).all():
        by_month[row.month][(row.club, row.platform)][row.metric] = row.value
    return by_month


# Additive across platforms: every row has exactly one platform.
_PLATFORM_ADDITIVE = (
    "events",
    "devices_active",
    "devices_new",
    "devices_returning",
    "devices_back",
    "devices_signed_in",
    "installs",
    "logins",
    "plans_made",
    "plans_completed",
    "map_views",
    "sessions",
    "pageviews",
)
_SESSION_BUCKETS = ("sessions_under_1m", "sessions_m1_to_5", "sessions_m5_to_20", "sessions_over_20m")
_EPSILON = 1e-6


def invariant_findings(db: Session, *, today: date | None = None) -> list[Finding]:
    """The sums that must hold in every month's figures. Exact, so any miss is a finding.

    With `today`, a month frozen longer than `MONTH_JUDGED_DAYS` is skipped,
    as the nightly run does; without it, every month is judged - which is
    what a test of the rollup's own arithmetic wants.
    """
    findings = []
    cells = _cells(db)
    frozen = frozen_months(db, today) if today is not None else set()
    for month, by_slice in sorted(cells.items()):
        total = by_slice.get((ALL, ALL))
        if total is None or month in frozen:
            continue
        platforms = [values for (club, platform), values in by_slice.items() if club == ALL and platform != ALL]

        def broken(name: str, observed: float, expected: float, *, status: str = "broken") -> None:
            findings.append(Finding(month, name, ALL, status, observed, expected))

        for metric in _PLATFORM_ADDITIVE:
            parts = sum(values.get(metric, 0.0) for values in platforms)
            if platforms and abs(parts - total.get(metric, 0.0)) > _EPSILON:
                broken(f"platforms_add_up:{metric}", parts, total.get(metric, 0.0))
        whole_app = {platform: values for (club, platform), values in by_slice.items() if club == ALL}
        for platform, values in sorted(whole_app.items()):
            split = sum(values.get(part, 0.0) for part in ("devices_new", "devices_returning", "devices_back"))
            if abs(split - values.get("devices_active", 0.0)) > _EPSILON:
                name = "growth_split_adds_up" if platform == ALL else f"growth_split_adds_up:{platform}"
                broken(name, split, values.get("devices_active", 0.0))
        buckets = sum(total.get(bucket, 0.0) for bucket in _SESSION_BUCKETS)
        if abs(buckets - total.get("sessions", 0.0)) > _EPSILON:
            broken("session_lengths_add_up", buckets, total.get("sessions", 0.0))
        devices = total.get("devices_active", 0.0)
        club_cells = [values for (club, platform), values in by_slice.items() if club != ALL]
        busiest = max((values.get("devices_active", 0.0) for values in club_cells), default=0.0)
        if busiest > devices + _EPSILON:
            broken("no_club_above_the_whole_app", busiest, devices)
        club_plans = sum(values.get("plans_made", 0.0) for values in club_cells)
        if club_plans > total.get("plans_made", 0.0) + 0.01:
            broken("club_plans_within_total", club_plans, total.get("plans_made", 0.0))
        # Loss, not a lie, can break these two - a phone's rows refused or
        # dropped from a full queue - so they warn rather than break.
        before = cells.get(add_months(month, -1), {}).get((ALL, ALL))
        if before is not None and total.get("devices_returning", 0.0) > before.get("devices_active", 0.0) + _EPSILON:
            broken("returning_within_last_month", total["devices_returning"], before.get("devices_active", 0.0), status="warn")
        if total.get("hikers_active", 0.0) > devices + _EPSILON:
            broken("hikers_within_phones", total["hikers_active"], devices, status="warn")
        late, events = total.get("events_after_close", 0.0), total.get("events", 0.0)
        if events and late / events > LATE_SHARE:
            broken("late_rows_after_close", late / events, LATE_SHARE, status="warn")
    return findings


def run_checks(db: Session, *, today: date, rollup_failed: bool = False) -> list[Finding]:
    """Every check, for the night of `today`. Writes nothing.

    `rollup_failed` is the workflow saying tonight's rollup step did not
    succeed - a fault the tables do not show until its heartbeat is
    `analytics_rollup_stale_days` old and collection pauses
    (app/routers/analytics.py).
    """
    arrivals = load_arrivals(db, today)
    failed_rollup = [Finding(today, "rollup_failed", ALL, "warn")] if rollup_failed else []
    return [
        *_volume_findings(arrivals, today),
        *_platform_findings(load_platform_arrivals(db, today), today),
        *_ratio_findings(arrivals, today),
        *_version_findings(db, today),
        *_intake_findings(db, today),
        *_pipeline_findings(db, today),
        *failed_rollup,
        *invariant_findings(db, today=today),
    ]


# Checks about a whole month, re-run over every month still judged every
# night - so tonight's run is the whole truth about them, whatever month they
# name, until the month is frozen (`frozen_months`).
MONTH_CHECKS = (
    "platforms_add_up",
    "growth_split_adds_up",
    "session_lengths_add_up",
    "no_club_above_the_whole_app",
    "club_plans_within_total",
    "returning_within_last_month",
    "hikers_within_phones",
    "late_rows_after_close",
    "month_not_closed",
)


def is_month_check(check_name: str) -> bool:
    return check_name.split(":")[0] in MONTH_CHECKS


# Every check not named after a metric. The usage report gives each a label
# of its own (scripts/usage_report.html `CHECK_NAMES`), and
# tests/test_analytics_report.py fails when one here has none.
NAMED_CHECKS = (
    "rows_refused",
    "rows_resent",
    "rows_over_budget",
    "rows_paused",
    "rows_unsealed_no_key",
    "rollup_failed",
    *MONTH_CHECKS,
)


# When two findings share a key - a check name cut to its column's width, or
# a scope two slices both reach - the one kept is the one worth reading first.
_SEVERITY = {"broken": 4, "zero": 3, "low": 2, "high": 2, "warn": 1}


def one_per_key(findings: list[Finding]) -> list[Finding]:
    """At most one finding per `analytics_anomalies` key, the most severe.

    Two in one insert would make Postgres refuse the whole statement
    (`ON CONFLICT DO UPDATE command cannot affect row a second time`), and
    with it every finding of the night.
    """
    kept: dict[tuple[date, str, str], Finding] = {}
    for finding in findings:
        held = kept.get(finding.key)
        if held is None or _SEVERITY.get(finding.status, 0) > _SEVERITY.get(held.status, 0):
            kept[finding.key] = finding
    return list(kept.values())


def record(db: Session, findings: list[Finding], *, today: date) -> list[Finding]:
    """Store tonight's findings, and return them.

    A finding tonight's run no longer makes is resolved, and removed rather
    than left standing: a month-level check re-judges every month not yet
    frozen, and the daily checks re-judge the last `EVALUATE_DAYS` days -
    late rows that filled a gap resolve the "low" they caused. A finding
    about an older day, or a frozen month, is history and stays until
    retention. One seen again keeps the night it first appeared.
    """
    findings = one_per_key(findings)
    window_start = today - timedelta(days=EVALUATE_DAYS)
    frozen = frozen_months(db, today)
    tonight = {finding.key for finding in findings}
    for stored in db.query(AnalyticsAnomaly).all():
        if is_month_check(stored.check_name):
            rejudged = stored.day not in frozen
        else:
            rejudged = stored.day >= window_start
        if rejudged and (stored.day, stored.check_name, stored.scope) not in tonight:
            db.delete(stored)
    if findings:
        table = AnalyticsAnomaly.__table__
        statement = insert(table).values(
            [
                {
                    "day": finding.day,
                    "check_name": finding.check_name[:48],
                    "scope": finding.scope[:64],
                    "status": finding.status,
                    "observed": finding.observed,
                    "expected": finding.expected,
                    "low": finding.low,
                    "high": finding.high,
                    "first_seen_on": today,
                    "last_seen_on": today,
                }
                for finding in sorted(findings, key=lambda f: f.key)
            ]
        )
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["day", "check_name", "scope"],
                set_={
                    name: statement.excluded[name] for name in ("status", "observed", "expected", "low", "high", "last_seen_on")
                },
            )
        )
    db.commit()
    return findings


def public_findings(db: Session, findings: list[Finding], *, today: date) -> list[Finding]:
    """What the public tracking issue may carry tonight: a statistical finding only from its second night.

    A finding judged against a noisy expectation (`STATISTICAL`) is held back
    the night it first appears, so one odd day costs nobody an email and
    late uploads get a night to resolve it. A sum that does not add up, or a
    pipeline fault, is not an estimate and goes in at once. The report shows
    every finding either way. Reads `first_seen_on`, so call it after `record`.
    """
    first_seen = {(row.day, row.check_name, row.scope): row.first_seen_on for row in db.query(AnalyticsAnomaly).all()}
    return [finding for finding in findings if finding.status not in STATISTICAL or first_seen.get(finding.key, today) < today]
