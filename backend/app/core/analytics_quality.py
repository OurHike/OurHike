"""Data quality for usage measurement: anomalies in each metric, and the sums that must hold (#1902).

Run every night after the rollup by .github/workflows/analytics-rollup.yml
(`scripts/analytics_quality.py`). Findings go into `analytics_anomalies`;
a check that comes out normal writes nothing. The usage report's data-quality
panel draws from here (app/core/analytics_report.py), and production's run
opens, updates or closes one tracking issue - which, the repository being
public, names checks and never figures.

WHAT IS CHECKED, AND WHY EACH ONE

1. **Each metric, each day, against the same weekday in the weeks before.**
   Installs, sign-ins, plans made and completed, map views, sessions,
   screens, and phones counted for the first time that week. Same weekday
   because hiking is a weekend activity and a Saturday is not a Tuesday;
   the median of up to `HISTORY_WEEKS` of them, so one odd week cannot drag
   the baseline.
2. **Compared lag for lag.** This app is offline-first: yesterday's count is
   missing everything still on a ridge. Each day is compared with earlier
   days *as they stood at the same age* - rows received within the same number
   of whole days of their date - which `received_on` makes exact. Whole days:
   the job runs mid-morning, so today's arrivals are partial and are left out
   on both sides. Without this, every fresh day reads low, every night, and
   the check is noise.
3. **Each event per session.** A release that stops recording plans shows up
   here as plans-per-session collapsing, even in a month when traffic is
   climbing for the season and the plain count looks fine.
4. **Each release against the others.** The same per-session rates, for one
   app version over a fortnight against every other version: the shape of a
   release that broke one event and nothing else.
5. **Intake.** Rows the server refused, by version (`analytics_intake`) -
   the only trace a refused row leaves - and resends.
6. **The pipeline.** Rows thrown away for want of a published key, a month
   left provisional past its close date (the rollup is not running), and
   closed months still collecting rows (`CLOSE_AFTER_DAYS` is too short).
7. **The sums that must hold**, on every month in `analytics_monthly`:
   platforms add up to the total, new + returning + back-again add up to the
   active phones, session lengths add up to sessions, no club has more phones
   than the whole app. A failure there is a bug or a lying client, not noise.

MISS RATHER THAN CRY WOLF

CLAUDE.md's rule for anything alert-shaped, and the reason every threshold
below asks for TWO things: an anomaly must be `Z` deviations out AND at least
`RELATIVE` away from what was expected. At a few events a day the first
alone fires on noise; at thousands, the second alone fires on a 3% wobble.
Too little history says `learning`, too few events says `quiet` - honest
non-answers rather than guesses. All of these numbers are @unvalidated:
picked, not measured, and what would settle them is a quarter of real data
and the maintainer's judgement of which findings were worth reading.
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
from app.models.analytics import AnalyticsAnomaly, AnalyticsMonth, AnalyticsMonthly, MonthStatus

# @unvalidated - see the module docstring for what would settle each.
Z = 4.0
RELATIVE = 0.5
MIN_EXPECTED = 10.0
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

# The daily series, by name. Each is a column of `_DAILY` below.
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

# Events checked per session, for instrumentation that broke quietly.
PER_SESSION = ("logins", "plans_made", "plans_completed", "map_views", "pageviews")

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
    if expected < MIN_EXPECTED:
        return "quiet", expected, low, high
    if observed == 0:
        return "zero", expected, low, high
    if observed < low:
        return "low", expected, low, high
    if observed > high:
        return "high", expected, low, high
    return "ok", expected, low, high


class Arrivals:
    """Daily counts, kept by the day rows arrived so any day can be read at any age."""

    def __init__(self, rows) -> None:
        self._by: dict[str, dict[date, list[tuple[date, float]]]] = {metric: defaultdict(list) for metric in DAILY_METRICS}
        self.first_day: date | None = None
        for row in rows:
            day, received = row["local_date"], row["received_on"]
            self.first_day = day if self.first_day is None else min(self.first_day, day)
            for metric in DAILY_METRICS:
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


def load_arrivals(db: Session, today: date) -> Arrivals:
    start = max(retention_start(today), today - timedelta(days=SERIES_DAYS + HISTORY_WEEKS * 7))
    return Arrivals(db.execute(_DAILY, {"start": start, "end": today}).mappings())


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


def _volume_findings(arrivals: Arrivals, today: date) -> list[Finding]:
    findings = []
    for metric in DAILY_METRICS:
        for item in daily_judgements(arrivals, metric, today, EVALUATE_DAYS):
            if item.status in ("low", "high", "zero"):
                findings.append(Finding(item.day, metric, ALL, item.status, item.observed, item.expected, item.low, item.high))
    return findings


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
            if status in ("low", "high", "zero"):
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
            scope = ALL if version == "*" else f"version:{version or 'unknown'}"
            if bad >= MIN_REFUSED_ROWS and total and bad / total >= limit:
                findings.append(Finding(day, "rows_refused", scope, "warn", bad / total, limit))
            accepted = outcomes["stored"] + outcomes["duplicate"]
            if version == "*" and accepted >= MIN_INTAKE_ROWS and outcomes["duplicate"] / accepted >= DUPLICATE_SHARE:
                findings.append(Finding(day, "rows_resent", ALL, "warn", outcomes["duplicate"] / accepted, DUPLICATE_SHARE))
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


def invariant_findings(db: Session) -> list[Finding]:
    """The sums that must hold in every month's figures. Exact, so any miss is a finding."""
    findings = []
    cells = _cells(db)
    for month, by_slice in sorted(cells.items()):
        total = by_slice.get((ALL, ALL))
        if total is None:
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


def run_checks(db: Session, *, today: date) -> list[Finding]:
    """Every check, for the night of `today`. Writes nothing."""
    arrivals = load_arrivals(db, today)
    return [
        *_volume_findings(arrivals, today),
        *_ratio_findings(arrivals, today),
        *_version_findings(db, today),
        *_intake_findings(db, today),
        *_pipeline_findings(db, today),
        *invariant_findings(db),
    ]


# Checks about a whole month, re-run over every month every night - so
# tonight's run is the whole truth about them, whatever month they name.
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


def record(db: Session, findings: list[Finding], *, today: date) -> list[Finding]:
    """Store tonight's findings, and return them.

    A finding tonight's run no longer makes is resolved, and removed rather
    than left standing: a month-level check re-judges every month, and the
    daily checks re-judge the last `EVALUATE_DAYS` days - late rows that
    filled a gap resolve the "low" they caused. A finding about an older day
    is history and stays until retention. One seen again keeps the night it
    first appeared.
    """
    window_start = today - timedelta(days=EVALUATE_DAYS)
    tonight = {(finding.day, finding.check_name, finding.scope) for finding in findings}
    for stored in db.query(AnalyticsAnomaly).all():
        rejudged = is_month_check(stored.check_name) or stored.day >= window_start
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
                for finding in sorted(findings, key=lambda f: (f.day, f.check_name, f.scope))
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
