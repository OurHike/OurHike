"""The monthly close and the six-month delete for usage events (#1902).

Run once a night by .github/workflows/analytics-rollup.yml
(`scripts/analytics_rollup.py`). Each run does three things, in this order,
in one transaction:

1. **Recomputes every open month** from its raw rows into `analytics_monthly`,
   replacing what was there. A provisional month is a projection, not a
   snapshot: recomputing it is how late arrivals get counted.
2. **Closes each month `CLOSE_AFTER_DAYS` after it ends.** A closed month is
   never recomputed again. Rows that arrive for it afterwards are counted in
   its `events_after_close` metric and nowhere else, so a published number
   does not move under a reader - it says how much it is missing instead.
3. **Deletes the raw rows of every month older than `RETENTION_MONTHS`**, and
   refuses to delete a month that has not closed. A month deleted before it
   closed would be numbers gone for good, so the job fails loudly instead and
   the month waits for a run that can close it first.

WHY A MONTH-END SNAPSHOT IS HARDER HERE THAN IT LOOKS, and where each answer is:

- Offline phones upload late -> step 1 and the provisional window.
- The delete could outrun the close -> step 3's refusal.
- Distinct counts do not add up across months -> each month's distinct counts
  are computed from its own rows and frozen at close; uniques across months
  come from `analytics_users.active_months`, which outlives the raw rows.
- "As of month end" figures (stocks) cannot be recomputed from a User table
  that kept moving -> `analytics_users` holds milestone DATES instead of flags.
- Which midnight -> the phone's own calendar day (`local_date`).
- A run that did not happen -> every run closes every month that is due, not
  "last month", so a week of missed runs is caught up by the next one.
- A definition that changes -> `DEFINITION_VERSION` on every month, so a
  number is never restated under a definition it was not computed with.

Exact, unmasked figures are written. The fewer-than-25 mask is applied when a
report is built (app/core/analytics_report.py) - the maintainer's "a mask at
runtime though. Dont mess with the data" (poll 2026-10-27).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.analytics import AnalyticsMonth, AnalyticsMonthly, MonthStatus

# "Event Metrics should only be stored for 6 months" - the maintainer's
# request of 2026-10-26. Counted in whole months: the current month and the
# six before it are held, so a row lives between six and seven months and
# never longer, and a month's rows go together.
RETENTION_MONTHS = 6

# Reasoned, @unvalidated. EVENTING.md §2 already treats "the most recent
# fortnight" as provisional on the same grounds - a phone offline for a
# section hike uploads when it next finds signal - and nobody has measured how
# late real uploads arrive. What would settle it: the `events_after_close`
# metric itself, a few months in. If closed months keep collecting more than a
# percent or two afterwards, this is too short.
CLOSE_AFTER_DAYS = 14

# Bumped whenever a metric below changes what it counts. A closed month keeps
# the version it was closed under.
DEFINITION_VERSION = 1

ALL = "*"


def month_start(day: date) -> date:
    return day.replace(day=1)


def add_months(month: date, months: int) -> date:
    index = month.year * 12 + (month.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def retention_start(today: date) -> date:
    """The first day whose rows may still be held: the month six before this one."""
    return add_months(month_start(today), -RETENTION_MONTHS)


def closes_on(month: date) -> date:
    """The first day a run may close `month`: `CLOSE_AFTER_DAYS` after it ends."""
    return add_months(month, 1) + timedelta(days=CLOSE_AFTER_DAYS)


@dataclass
class RollupResult:
    recomputed: list[date] = field(default_factory=list)
    closed: list[date] = field(default_factory=list)
    late_counted: list[date] = field(default_factory=list)
    deleted: dict[date, int] = field(default_factory=dict)
    # Months past retention that could not be deleted because they never
    # closed. Non-empty means the run failed (scripts/analytics_rollup.py).
    refused: list[date] = field(default_factory=list)


# Every metric on the all-clubs slices, by platform and overall. The column
# names ARE the metric names, so this query is the one definition of each.
_SLICE_METRICS = text(
    """
    select
      platform,
      count(*) filter (where month_first) as devices_active,
      count(*) filter (where ever_first) as devices_new,
      count(distinct user_key) as hikers_active,
      count(*) filter (where event = 'app_installed') as installs,
      count(*) filter (where event = 'user_login') as logins,
      count(distinct user_key) filter (where event = 'user_login') as login_hikers,
      count(*) filter (where event = 'hike_plan_made') as plans_made,
      coalesce(sum(miles) filter (where event = 'hike_plan_made'), 0) as plan_miles,
      count(distinct user_key) filter (where event = 'hike_plan_made') as plan_hikers,
      count(*) filter (where event = 'hike_plan_completed') as plans_completed,
      coalesce(sum(miles) filter (where event = 'hike_plan_completed'), 0) as completed_miles,
      count(distinct user_key) filter (where event = 'hike_plan_completed') as completion_hikers,
      count(*) filter (where event = 'map_screen_viewed') as map_views,
      count(distinct user_key) filter (where event = 'map_screen_viewed') as map_view_hikers,
      count(*) filter (where event = 'session') as sessions,
      coalesce(sum(pageviews) filter (where event = 'session'), 0) as pageviews,
      count(*) filter (where session_length = 'under_1m') as sessions_under_1m,
      count(*) filter (where session_length = 'm1_to_5') as sessions_m1_to_5,
      count(*) filter (where session_length = 'm5_to_20') as sessions_m5_to_20,
      count(*) filter (where session_length = 'over_20m') as sessions_over_20m,
      count(*) as events,
      count(*) filter (where user_key is not null) as events_identified,
      count(*) filter (where has_fix) as fixes,
      count(*) filter (where seal = 'no_key') as unsealed_no_key
    from analytics_events
    where local_date >= :start and local_date < :end
    group by grouping sets ((), (platform))
    """
)

# A club's share of each event it was about. Plans are split by their miles
# in each club ("assigned by # miles specific for each club", poll
# 2026-10-27), so a 30-mile plan with 20 miles in one club counts as two
# thirds of a plan there, and its planned miles land where they were walked.
# Totals across clubs therefore add up to the events that had a club, rather
# than to more than that.
_CLUB_METRICS = text(
    """
    select
      c.club,
      count(distinct e.user_key) as hikers_active,
      coalesce(sum(c.share) filter (where e.event = 'user_login'), 0) as logins,
      coalesce(sum(c.share) filter (where e.event = 'hike_plan_made'), 0) as plans_made,
      coalesce(sum(c.share * coalesce(e.miles, 0)) filter (where e.event = 'hike_plan_made'), 0) as plan_miles,
      count(distinct e.user_key) filter (where e.event = 'hike_plan_made') as plan_hikers,
      coalesce(sum(c.share) filter (where e.event = 'hike_plan_completed'), 0) as plans_completed,
      coalesce(sum(c.share * coalesce(e.miles, 0)) filter (where e.event = 'hike_plan_completed'), 0)
        as completed_miles,
      count(distinct e.user_key) filter (where e.event = 'hike_plan_completed') as completion_hikers,
      coalesce(sum(c.share) filter (where e.event = 'map_screen_viewed'), 0) as map_views,
      coalesce(sum(c.share) filter (where e.event = 'session'), 0) as sessions
    from analytics_events e
    cross join lateral (
      select key as club, value::float as share from json_each_text(e.clubs)
    ) c
    where e.clubs is not null and e.local_date >= :start and e.local_date < :end
    group by c.club
    """
)

# Devices active on a club's trails, from the phone's own "first time this
# month in this club" answer - EVENTING.md §2's trick, per club, so it counts
# hikers who said no as exactly as hikers who said yes.
_CLUB_DEVICES = text(
    """
    select f.club, count(*) as devices_active
    from analytics_events e
    cross join lateral json_array_elements_text(e.club_firsts) as f(club)
    where e.club_firsts is not null and e.local_date >= :start and e.local_date < :end
    group by f.club
    """
)

_HIKERS_NEW = text("select count(*) from analytics_users where first_seen_on >= :start and first_seen_on < :end")

_EVENTS_AFTER_CLOSE = text(
    """
    select count(*) from analytics_events
    where local_date >= :start and local_date < :end and received_on > :closed_on
    """
)


def _metric_rows(month: date, club: str, platform: str, values: dict) -> Iterable[AnalyticsMonthly]:
    for metric, value in values.items():
        if metric in ("platform", "club"):
            continue
        yield AnalyticsMonthly(month=month, metric=metric, club=club, platform=platform, value=float(value or 0))


def compute_month(db: Session, month: date) -> list[AnalyticsMonthly]:
    """Every metric for `month`, from its raw rows. Writes nothing."""
    bounds = {"start": month, "end": add_months(month, 1)}
    rows: list[AnalyticsMonthly] = []

    for row in db.execute(_SLICE_METRICS, bounds).mappings():
        values = dict(row)
        platform = values["platform"] or ALL
        if platform == ALL:
            values["hikers_new"] = db.execute(_HIKERS_NEW, bounds).scalar_one()
        rows.extend(_metric_rows(month, ALL, platform, values))

    by_club: dict[str, dict] = {}
    for row in db.execute(_CLUB_METRICS, bounds).mappings():
        by_club[row["club"]] = dict(row)
    for row in db.execute(_CLUB_DEVICES, bounds).mappings():
        by_club.setdefault(row["club"], {})["devices_active"] = row["devices_active"]
    for club, values in sorted(by_club.items()):
        values.setdefault("devices_active", 0)
        rows.extend(_metric_rows(month, club, ALL, values))

    return rows


def _replace_month(db: Session, month: date, rows: list[AnalyticsMonthly]) -> None:
    db.query(AnalyticsMonthly).filter(AnalyticsMonthly.month == month).delete(synchronize_session=False)
    db.add_all(rows)


def _count_late(db: Session, state: AnalyticsMonth) -> None:
    """Refresh a closed month's `events_after_close`, the only number it still moves."""
    month = state.month
    late = db.execute(
        _EVENTS_AFTER_CLOSE,
        {"start": month, "end": add_months(month, 1), "closed_on": state.closed_at.date()},
    ).scalar_one()
    db.query(AnalyticsMonthly).filter(
        AnalyticsMonthly.month == month,
        AnalyticsMonthly.metric == "events_after_close",
        AnalyticsMonthly.club == ALL,
        AnalyticsMonthly.platform == ALL,
    ).delete(synchronize_session=False)
    db.add(AnalyticsMonthly(month=month, metric="events_after_close", club=ALL, platform=ALL, value=float(late)))


def run(db: Session, *, today: date | None = None, now: datetime | None = None) -> RollupResult:
    """One night's work. Commits once at the end, or not at all."""
    now = now or utc_now()
    today = today or now.date()
    result = RollupResult()

    held_months = [
        row[0]
        for row in db.execute(text("select distinct date_trunc('month', local_date)::date from analytics_events order by 1"))
    ]
    states = {state.month: state for state in db.query(AnalyticsMonth).all()}
    open_months = {month for month, state in states.items() if state.status == MonthStatus.provisional}

    for month in sorted(set(held_months) | open_months):
        state = states.get(month)
        if state is not None and state.status == MonthStatus.closed:
            if state.raw_deleted_at is None:
                _count_late(db, state)
                result.late_counted.append(month)
            continue

        _replace_month(db, month, compute_month(db, month))
        result.recomputed.append(month)
        if state is None:
            state = AnalyticsMonth(month=month, status=MonthStatus.provisional, definition_version=DEFINITION_VERSION)
            db.add(state)
            states[month] = state
        state.computed_at = now
        state.definition_version = DEFINITION_VERSION
        if today >= closes_on(month):
            state.status = MonthStatus.closed
            state.closed_at = now
            result.closed.append(month)

    cutoff = retention_start(today)
    for month in held_months:
        if month >= cutoff:
            continue
        state = states.get(month)
        if state is None or state.status != MonthStatus.closed:
            result.refused.append(month)
            continue
        deleted = db.execute(
            text("delete from analytics_events where local_date >= :start and local_date < :end"),
            {"start": month, "end": add_months(month, 1)},
        ).rowcount
        state.raw_deleted_at = now
        result.deleted[month] = deleted

    db.commit()
    return result
