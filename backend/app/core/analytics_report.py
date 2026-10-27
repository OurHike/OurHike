"""What the usage report shows, and the fewer-than-25 mask it applies (#1902).

`scripts/usage_report.py` turns this into one self-contained HTML file: the
dashboard the maintainer chose (poll 2026-10-27, "Python -> one HTML file"),
in OurHike's style, filterable by date and by club. This module is the half
worth testing: which figures leave the database, and which are masked first.

THE MASK IS APPLIED HERE, AT BUILD TIME, AND NEVER STORED

"A mask at runtime though. Dont mess with the data" (the maintainer, poll
2026-10-27). `analytics_monthly` keeps exact figures; every report built from
it masks the same way, and the masked value is never written into the file -
not hidden by the page's script, absent - so a report forwarded to a club
cannot be read past its mask with view-source.

The rules, each a way a small number would otherwise describe people:

1. **A cell describing 1 to `K_FLOOR` - 1 devices is masked whole.** A
   month's figures for one club, or one platform, all describe the same few
   people, so a club-month with 9 active devices shows no plans, miles or
   map views either. A cell of no devices is shown as the zeros it holds: it
   describes nobody, and hiding it would hide the next platform with it
   (rule 3) for no reason - an app with no web users lost its smaller
   mobile platform that way. Anything in it that is not zero describes
   phones nobody counted, and is masked.
2. **A count of people inside a shown cell is masked below `K_FLOOR`** -
   hikers who said yes, and phones that did one thing (made a plan, came
   back, are signed in) - since 900 devices and 12 of them linked is a cell
   whose "12" describes twelve people. **So is one whose complement is below
   it**: of 900 phones, "880 viewed the map" says 20 did not, as surely as if
   the 20 were printed. New, returning and back-again phones add up to the
   cell's active phones exactly, so when any one of the three is masked, all
   three are. **The events those people made go with them** (`FOLLOWERS`):
   a month's installs is its new phones near enough, so `installs` beside a
   masked `devices_new` would print the number the mask hid. And returning
   phones are a subset of LAST month's active ones too, so they are masked
   when the phones lost since then are under `K_FLOOR` - the page's "lost
   since last month" is that subtraction, done here (`devices_lost`).
3. **Complementary suppression, so nothing hidden comes back by
   subtraction.** Platforms add up to the whole app exactly, so a month's
   hidden platforms are hidden together until they hold `K_FLOOR` people
   between them - two hidden platforms of 10 and 5 would otherwise come back
   as a 15 - and a metric masked inside one platform is masked in the
   next-smallest platform too. Clubs: when exactly one club is masked in a
   month and the all-clubs total is shown, the next-smallest is masked too.
   Club shares only add up to the events that had a club, so subtraction
   there is already blurred by the events that had none; this closes it
   anyway, because "blurred" is a guess about the data and the rule is not.

`K_FLOOR = 25` is EVENTING.md §6's floor, kept by the maintainer for club
cells on 2026-10-27 ("<25" everywhere, over exact-for-you and over lowering
it to 10). It is still @unvalidated as a number: §6 says why a floor, not why
this one, and what would settle it is somebody with a disclosure-control
background looking at the slices this report actually publishes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import analytics_quality as quality
from app.core import analytics_storage
from app.core.analytics_rollup import ALL, add_months, closes_on
from app.core.time import utc_now
from app.models.analytics import (
    AnalyticsAnomaly,
    AnalyticsMonth,
    AnalyticsMonthly,
    AnalyticsSealKey,
    AnalyticsUser,
    MonthStatus,
)

K_FLOOR = 25

# The metric a cell's people are counted by. Every slice has it: the phones'
# own "first this month" answers, overall, per platform and per club.
PEOPLE = "devices_active"

# Counts of hikers who said yes - rule 2. All but the first are subsets of
# `hikers_active`, so their complements in it are masked too.
HIKER_COUNTS = frozenset({"hikers_active", "hikers_new", "login_hikers", "plan_hikers", "completion_hikers", "map_view_hikers"})
HIKER_SUBSETS = HIKER_COUNTS - {"hikers_active"}

# Counts of phones inside a cell - rule 2 again, each a subset of PEOPLE.
DEVICE_COUNTS = frozenset(
    {
        "devices_new",
        "devices_returning",
        "devices_back",
        "devices_signed_in",
        "devices_login",
        "devices_plan_made",
        "devices_plan_completed",
        "devices_map_view",
    }
)
# PEOPLE splits exactly into these: one masked part could be had from the rest.
GROWTH_PARTS = ("devices_new", "devices_returning", "devices_back")

# The events a count of people made, masked whenever that count is (rule 2).
FOLLOWERS = {
    "devices_new": ("installs",),
    "devices_plan_made": ("plans_made", "plan_miles"),
    "devices_plan_completed": ("plans_completed", "completed_miles"),
    "devices_login": ("logins",),
    "devices_map_view": ("map_views",),
    "hikers_active": ("events_identified",),
}

# Counts of events, not of people. An event count under the floor was made by
# fewer than the floor, so it is masked whatever cell it is in - which is
# what masks a club's plans, completions, sign-ins and map views at all: a
# club cell has no count of phones per kind of event for `FOLLOWERS` to read,
# so "GATC: 1 plan, 12.5 miles" was one hiker's plan, printed, and the
# whole-app figure masked beside it could be read back from it (#1903's
# second review). The data-health counts are events too.
EVENT_COUNTS = frozenset(
    {
        "installs",
        "logins",
        "plans_made",
        "plans_completed",
        "map_views",
        "sessions",
        "pageviews",
        "sessions_under_1m",
        "sessions_m1_to_5",
        "sessions_m5_to_20",
        "sessions_over_20m",
        "events",
        "events_identified",
        "fixes",
        "unsealed_no_key",
        "events_after_close",
    }
)
# What an event count carries with it, masked whenever it is.
EVENT_FOLLOWERS = {
    "plans_made": ("plan_miles",),
    "plans_completed": ("completed_miles",),
    "sessions": ("pageviews",),
}
# `sessions` splits exactly into these: one masked part could be had from the
# rest, as "2 visits over 20 minutes" was from the web cell's other three.
SESSION_PARTS = ("sessions_under_1m", "sessions_m1_to_5", "sessions_m5_to_20", "sessions_over_20m")

# Phones counted last month and not this one, on the all-clubs total:
# computed here, masked by the same floor, and drawn by the page as it is.
LOST = "devices_lost"

# How far back a report reaches by default. Monthly figures are kept
# indefinitely; two years is what one page can draw legibly.
DEFAULT_MONTHS = 24

# Cohorts for the retention table: hikers who said yes, by the month they were
# first seen, followed for this many months after.
COHORT_MONTHS = 12
COHORT_FOLLOW = 6

# How far back the data-quality panel lists findings.
FINDINGS_DAYS = 60


def _cell_key(month: date, club: str, platform: str) -> str:
    return f"{month:%Y-%m}|{club}|{platform}"


def _previous(month_key: str) -> str:
    """'2026-10' -> '2026-09'."""
    return f"{add_months(date.fromisoformat(f'{month_key}-01'), -1):%Y-%m}"


def _small(count: float) -> bool:
    """Describes somebody, and fewer than the floor. Zero describes nobody."""
    return 0 < count < K_FLOOR


def mask_cells(cells: dict[str, dict[str, float]]) -> tuple[dict[str, dict[str, float | None]], set[str]]:
    """Apply the three rules. Returns the masked cells and the keys masked whole.

    A masked value is `None`, which the page draws as "<25". A zero stays a
    zero: a count of nobody describes nobody. The all-clubs total of each
    month gains `devices_lost` (`LOST`), already masked.
    """
    masked: dict[str, dict[str, float | None]] = {}
    whole: set[str] = set()

    def hide_whole(key: str) -> None:
        masked[key] = {metric: None for metric in cells[key]}
        whole.add(key)

    # Rule 1, and rule 2 inside every cell that survives it.
    for key, metrics in cells.items():
        people = metrics.get(PEOPLE, 0) or 0
        if _small(people):
            hide_whole(key)
            continue
        if people == 0:
            # Its zeros describe nobody. Anything else in it describes phones
            # nobody counted - a first row of the month still on a ridge - so
            # it is masked rather than shown beside a zero that cannot cover it.
            masked[key] = {metric: (None if value else value) for metric, value in metrics.items()}
            continue
        hikers = metrics.get("hikers_active", 0) or 0
        shown: dict[str, float | None] = {}
        for metric, value in metrics.items():
            count = value or 0
            if metric in HIKER_COUNTS and _small(count):
                shown[metric] = None
            elif metric in HIKER_SUBSETS and _small(hikers - count):
                shown[metric] = None
            elif metric in DEVICE_COUNTS and (_small(count) or _small(people - count)):
                shown[metric] = None
            elif metric in EVENT_COUNTS and _small(count):
                shown[metric] = None
            else:
                shown[metric] = value
        masked[key] = shown

    # Rule 3 for whole cells, within each month: clubs, then platforms.
    clubs: dict[str, list[str]] = defaultdict(list)
    platforms: dict[str, list[str]] = defaultdict(list)
    for key in cells:
        month, club, platform = key.split("|")
        if club != ALL and platform == ALL:
            clubs[month].append(key)
        elif club == ALL and platform != ALL:
            platforms[month].append(key)

    def people_of(key: str) -> float:
        return cells[key].get(PEOPLE, 0) or 0

    def total_shown(month: str) -> bool:
        total = f"{month}|{ALL}|{ALL}"
        return total in cells and total not in whole

    # A cell of nobody adds nothing to what is hidden beside it, so it is
    # never the one picked, for a club or a platform.
    for month, keys in clubs.items():
        hidden = [key for key in keys if key in whole]
        shown_keys = [key for key in keys if key not in whole and people_of(key) > 0]
        if len(hidden) == 1 and shown_keys and total_shown(month):
            hide_whole(min(shown_keys, key=people_of))
    for month, keys in platforms.items():
        if not total_shown(month):
            continue
        candidates = sorted((key for key in keys if key not in whole and people_of(key) > 0), key=people_of)
        while any(key in whole for key in keys) and sum(people_of(key) for key in keys if key in whole) < K_FLOOR:
            if not candidates:
                break
            hide_whole(candidates.pop(0))

    # Rule 2's linked masks and rule 3 for single metrics, until nothing moves:
    # each can mask a metric another rule then has to follow.
    changed = True

    def hide(key: str, metric: str) -> None:
        nonlocal changed
        if metric in masked[key] and masked[key][metric] is not None:
            masked[key][metric] = None
            changed = True

    while changed:
        changed = False
        for key, shown in masked.items():
            if key in whole:
                continue
            for parts in (GROWTH_PARTS, SESSION_PARTS):
                if any(part in shown and shown[part] is None for part in parts):
                    for part in parts:
                        hide(key, part)
            for people, events in (*FOLLOWERS.items(), *EVENT_FOLLOWERS.items()):
                if people in shown and shown[people] is None:
                    for event in events:
                        hide(key, event)
            # Returning phones against last month's: the page's "lost since
            # last month" is exactly this subtraction.
            month, club, platform = key.split("|")
            before = masked.get(f"{_previous(month)}|{club}|{platform}", {}).get(PEOPLE)
            returning = shown.get("devices_returning")
            if before is not None and returning is not None and _small(before - returning):
                hide(key, "devices_returning")

        for month, keys in platforms.items():
            total = f"{month}|{ALL}|{ALL}"
            if not total_shown(month):
                continue
            for metric, value in masked[total].items():
                if value is None:
                    continue
                hidden = [key for key in keys if metric in masked[key] and masked[key][metric] is None]
                if len(hidden) != 1:
                    continue
                candidates = [
                    key
                    for key in keys
                    if key not in whole and key not in hidden and masked[key].get(metric) is not None and people_of(key) > 0
                ]
                if candidates:
                    # The next-smallest, preferring one whose own figure is not
                    # zero: hiding a zero beside the masked figure hides nothing.
                    hide(min(candidates, key=lambda key: ((cells[key].get(metric) or 0) == 0, people_of(key))), metric)

    # Lost since last month, on the all-clubs total of every month whose
    # previous month is in the report too.
    for key in cells:
        month, club, platform = key.split("|")
        before_key = f"{_previous(month)}|{ALL}|{ALL}"
        if club != ALL or platform != ALL or before_key not in cells:
            continue
        before = masked[before_key].get(PEOPLE)
        returning = masked[key].get("devices_returning")
        if before is None or returning is None:
            masked[key][LOST] = None
        else:
            lost = max(0.0, before - returning)
            masked[key][LOST] = None if _small(lost) else lost

    return masked, whole


def _cohorts(db: Session, latest: date) -> list[dict]:
    """Retention of hikers who said yes, by the month they were first seen.

    Read from `analytics_users.active_months`, which outlives the raw rows -
    the reason that column exists. A cohort under `K_FLOOR` is masked whole,
    by rule 1's reasoning; inside one, a count is masked when it, or the
    cohort less it, is under `K_FLOOR` - rule 2's complement, since of 30
    hikers "28 came back" says 2 did not.
    """
    first = add_months(latest, -(COHORT_MONTHS - 1))
    users = db.execute(
        select(AnalyticsUser.first_seen_on, AnalyticsUser.active_months).where(AnalyticsUser.first_seen_on >= first)
    ).all()

    by_cohort: dict[int, list[set[int]]] = defaultdict(list)
    for first_seen, active in users:
        by_cohort[first_seen.year * 100 + first_seen.month].append(set(active or ()))

    rows = []
    for offset in range(COHORT_MONTHS):
        cohort = add_months(first, offset)
        if cohort > latest:
            break
        members = by_cohort.get(cohort.year * 100 + cohort.month, [])
        size = len(members)
        retained: list[float | None] = []
        for after in range(1, COHORT_FOLLOW + 1):
            later = add_months(cohort, after)
            if later > latest:
                break
            count = sum(1 for months in members if later.year * 100 + later.month in months)
            hidden = size < K_FLOOR or _small(count) or _small(size - count)
            retained.append(None if hidden else (count / size if size else 0.0))
        rows.append({"cohort": f"{cohort:%Y-%m}", "size": None if _small(size) else size, "retained": retained})
    return rows


def _user_table(db: Session) -> dict[str, int | None]:
    """The User table as of now: stocks, which its milestone dates answer.

    Rule 2 with its complement: the hikers who ever planned are a subset of
    the hikers, so "28 of 30 ever planned" is masked as surely as "2 did".
    """
    hikers, ever_planned, ever_completed = db.execute(
        select(
            func.count(),
            func.count(AnalyticsUser.first_plan_on),
            func.count(AnalyticsUser.first_completion_on),
        )
    ).one()
    return {
        "hikers": None if _small(hikers) else hikers,
        "ever_planned": None if _small(ever_planned) or _small(hikers - ever_planned) else ever_planned,
        "ever_completed": None if _small(ever_completed) or _small(hikers - ever_completed) else ever_completed,
    }


def _storage(db: Session) -> dict:
    """The storage strip at the top of the data-quality panel (app/core/analytics_storage.py).

    Rows held as a share, in whole percent, and the room on disk in whole
    megabytes: never the row count, which two reports a day apart would
    turn into the day's stored rows. A whole percent of the 250 MB ceiling is
    about 6,900 rows, and a megabyte about 2,700, so a day's difference stays
    inside the rounding at this app's size.
    """
    storage = analytics_storage.measure(db)
    megabytes = 1024 * 1024
    return {
        "rows": _gauge(storage.rows_share),
        "usage": _gauge(
            storage.usage_share, mb=round(storage.usage_bytes / megabytes), of_mb=settings.analytics_storage_ceiling_mb
        ),
        "database": _gauge(storage.quota_share, mb=round(storage.database_bytes / megabytes), of_mb=settings.database_quota_mb),
        "warn_share": quality.STORAGE_WARN_SHARE,
    }


def _gauge(share: float | None, **sizes: int) -> dict:
    """One limit's share, and its status judged here by the nightly checks' own line, so the page judges nothing."""
    if share is None:
        return {**sizes, "share": None, "status": None}
    return {**sizes, "share": round(share, 2), "status": "warn" if share >= quality.STORAGE_WARN_SHARE else "ok"}


def _quality(db: Session, today: date) -> dict:
    """The data-quality panel: each metric's days, and how each was judged.

    A SHARE, NEVER A COUNT, AND NOT ALWAYS THAT. The panel answers "is this
    normal", which a status and a ratio to the expected value answer, and a
    forwarded report then carries no daily figure to read a small number out
    of. The share is published only where `expected` is at least `K_FLOOR`,
    and the band the checks judged against is not published at all: its
    edges are worked out from the count itself, and the review that removed
    them recovered the exact daily count from `high / expected = 1 + 4/√E` on
    50 of 56 days. The page draws the fixed half of the test instead - `band`,
    1 - RELATIVE to 1 + RELATIVE - which depends on no count.
    """
    arrivals = quality.load_arrivals(db, today)
    series = {}
    for metric in quality.VOLUME_METRICS:
        points = []
        for item in quality.daily_judgements(arrivals, metric, today, quality.SERIES_DAYS):
            judged = item.status not in ("learning", "quiet")
            shareable = judged and item.expected is not None and item.expected >= K_FLOOR
            points.append(
                {
                    "day": item.day.isoformat(),
                    "status": item.status,
                    "share": round(item.observed / item.expected, 3) if shareable else None,
                }
            )
        series[metric] = points
    findings = [
        {
            "day": row.day.isoformat(),
            "check": row.check_name,
            "scope": row.scope,
            "status": row.status,
            "first_seen": row.first_seen_on.isoformat(),
            "last_seen": row.last_seen_on.isoformat(),
        }
        for row in db.query(AnalyticsAnomaly)
        .filter(AnalyticsAnomaly.day >= today - timedelta(days=FINDINGS_DAYS))
        .order_by(AnalyticsAnomaly.day.desc(), AnalyticsAnomaly.check_name)
        .all()
    ]
    return {
        "series": series,
        "findings": findings,
        "metrics": list(quality.VOLUME_METRICS),
        "band": [1 - quality.RELATIVE, 1 + quality.RELATIVE],
        "storage": _storage(db),
    }


def build_report_data(db: Session, *, environment: str, months: int = DEFAULT_MONTHS, today: date | None = None) -> dict:
    """Everything the page draws, masked, as plain JSON-ready values."""
    today = today or utc_now().date()
    states = db.query(AnalyticsMonth).order_by(AnalyticsMonth.month.desc()).limit(months).all()
    states.reverse()
    if not states:
        return {
            "generated_at": utc_now().isoformat() + "Z",
            "environment": environment,
            "floor": K_FLOOR,
            "months": [],
            "clubs": [],
            "cells": {},
            "masked": [],
            "cohorts": [],
            "users": _user_table(db),
            "keys_published_through": None,
            "quality": _quality(db, today),
            "today": today.isoformat(),
        }

    month_list = [state.month for state in states]
    cells: dict[str, dict[str, float]] = defaultdict(dict)
    for row in db.query(AnalyticsMonthly).filter(AnalyticsMonthly.month.in_(month_list)).all():
        cells[_cell_key(row.month, row.club, row.platform)][row.metric] = row.value
    masked, whole = mask_cells(dict(cells))

    clubs = sorted({key.split("|")[1] for key in cells if key.split("|")[1] != ALL})
    last_key = db.query(AnalyticsSealKey.month).order_by(AnalyticsSealKey.month.desc()).first()

    return {
        "generated_at": utc_now().isoformat() + "Z",
        "environment": environment,
        "floor": K_FLOOR,
        "months": [
            {
                "month": f"{state.month:%Y-%m}",
                "status": state.status.value if isinstance(state.status, MonthStatus) else state.status,
                "closes_on": closes_on(state.month).isoformat(),
                "raw_deleted": state.raw_deleted_at is not None,
                "definition_version": state.definition_version,
            }
            for state in states
        ],
        "clubs": clubs,
        "cells": masked,
        "masked": sorted(whole),
        "cohorts": _cohorts(db, month_list[-1]),
        "users": _user_table(db),
        "keys_published_through": f"{last_key[0]:%Y-%m}" if last_key else None,
        "quality": _quality(db, today),
        "today": today.isoformat(),
    }
