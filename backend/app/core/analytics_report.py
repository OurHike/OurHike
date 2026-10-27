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

Three rules, each a way a small number would otherwise describe people:

1. **A cell describing fewer than `K_FLOOR` devices is masked whole.** A
   month's figures for one club, or one platform, all describe the same few
   people, so a club-month with 9 active devices shows no plans, miles or
   map views either.
2. **A count of hikers who said yes is masked below `K_FLOOR`**, even in a
   cell that is otherwise shown - 900 devices and 12 of them linked is a cell
   whose "12" describes twelve people.
3. **Complementary suppression.** When exactly one club (or one platform)
   is masked in a month and the all-clubs total is shown, the next-smallest
   is masked too, so the hidden one cannot be had by subtraction. Club
   shares only add up to the events that had a club, so subtraction there is
   already blurred by the events that had none; this closes it anyway,
   because "blurred" is a guess about the data and the rule is not.

`K_FLOOR = 25` is EVENTING.md §6's floor, kept by the maintainer for club
cells on 2026-10-27 ("<25" everywhere, over exact-for-you and over lowering
it to 10). It is still @unvalidated as a number: §6 says why a floor, not why
this one, and what would settle it is somebody with a disclosure-control
background looking at the slices this report actually publishes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.analytics_rollup import ALL, add_months, closes_on
from app.core.time import utc_now
from app.models.analytics import AnalyticsMonth, AnalyticsMonthly, AnalyticsSealKey, AnalyticsUser, MonthStatus

K_FLOOR = 25

# The metric a cell's people are counted by. Every slice has it: the phones'
# own "first this month" answers, overall, per platform and per club.
PEOPLE = "devices_active"

# Counts of hikers who said yes - rule 2.
HIKER_COUNTS = frozenset({"hikers_active", "hikers_new", "login_hikers", "plan_hikers", "completion_hikers", "map_view_hikers"})

# How far back a report reaches by default. Monthly figures are kept
# indefinitely; two years is what one page can draw legibly.
DEFAULT_MONTHS = 24

# Cohorts for the retention table: hikers who said yes, by the month they were
# first seen, followed for this many months after.
COHORT_MONTHS = 12
COHORT_FOLLOW = 6


def _cell_key(month: date, club: str, platform: str) -> str:
    return f"{month:%Y-%m}|{club}|{platform}"


def mask_cells(cells: dict[str, dict[str, float]]) -> tuple[dict[str, dict[str, float | None]], set[str]]:
    """Apply the three rules. Returns the masked cells and the keys masked whole.

    A masked value is `None`, which the page draws as "<25". A zero stays a
    zero: a count of nobody describes nobody.
    """
    masked: dict[str, dict[str, float | None]] = {}
    whole: set[str] = set()

    for key, metrics in cells.items():
        people = metrics.get(PEOPLE, 0) or 0
        if people < K_FLOOR:
            masked[key] = {metric: None for metric in metrics}
            whole.add(key)
            continue
        masked[key] = {
            metric: (None if metric in HIKER_COUNTS and 0 < (value or 0) < K_FLOOR else value)
            for metric, value in metrics.items()
        }

    # Rule 3: within each month, across clubs and across platforms.
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for key in cells:
        month, club, platform = key.split("|")
        if club != ALL and platform == ALL:
            groups[(month, "club")].append(key)
        elif club == ALL and platform != ALL:
            groups[(month, "platform")].append(key)
    for (month, _kind), keys in groups.items():
        total = f"{month}|{ALL}|{ALL}"
        hidden = [key for key in keys if key in whole]
        shown = [key for key in keys if key not in whole]
        if len(hidden) == 1 and shown and total in cells and total not in whole:
            smallest = min(shown, key=lambda key: cells[key].get(PEOPLE, 0) or 0)
            masked[smallest] = {metric: None for metric in cells[smallest]}
            whole.add(smallest)

    return masked, whole


def _cohorts(db: Session, latest: date) -> list[dict]:
    """Retention of hikers who said yes, by the month they were first seen.

    Read from `analytics_users.active_months`, which outlives the raw rows -
    the reason that column exists. Each count below `K_FLOOR` is masked, the
    cohort's size included, by rule 1's reasoning.
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
            retained.append(None if 0 < count < K_FLOOR or size < K_FLOOR else (count / size if size else 0.0))
        rows.append({"cohort": f"{cohort:%Y-%m}", "size": None if 0 < size < K_FLOOR else size, "retained": retained})
    return rows


def _user_table(db: Session) -> dict[str, int | None]:
    """The User table as of now: stocks, which its milestone dates answer."""
    hikers, ever_planned, ever_completed = db.execute(
        select(
            func.count(),
            func.count(AnalyticsUser.first_plan_on),
            func.count(AnalyticsUser.first_completion_on),
        )
    ).one()
    figures = {"hikers": hikers, "ever_planned": ever_planned, "ever_completed": ever_completed}
    return {name: (None if 0 < value < K_FLOOR else value) for name, value in figures.items()}


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
        "today": today.isoformat(),
    }
