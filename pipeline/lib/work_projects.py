"""The shape of a reviewed volunteer work project, and what makes one
publishable.

features/VOLUNTEERING.md Phase B (#760) is the design; this is the half a
test can run. It owns one question - **is this row safe to send a hiker
toward?** - and answers it for the reviewed file
(`reference/work_projects.json`) before `export_work_projects.py` bakes
anything. The stakes are lib/atc_updates.py's in a different costume: a
wrong closure strands somebody at a barrier that is not there, and a wrong
workday sends somebody to a trailhead on a Saturday for nothing.

WHERE THE ROWS COME FROM, AND UNTIL WHEN. A reviewed file in git is the
stopgap the design names outright - "it does not scale past a handful of
early-partner clubs, and it does not have to". Club admin tooling
(VOLUNTEERING.md Phase E) replaces this file's production rows; the shape
below is the shape that tooling will emit, so the client never learns two.

THE SAMPLE ROWS ARE A SECOND CITIZEN, DELIBERATELY. Maintainer decision
2026-08-20 (recorded on #760): the mechanism ships end to end with clearly
marked sample rows that publish to the UA environment only - production gets
this file's `rows`, which stay empty until a real club supplies real
workdays. No invented workday may reach a hiker: a person driving to a
trailhead for an event nobody scheduled is this feature's own failure mode,
self-inflicted. Samples therefore live under a separate key, carry relative
dates (`starts_in_days`) so UA always has rows inside the fourteen-day
window however long ago the file was edited, and are excluded whenever the
environment is production - or unknown, because the conservative reading of
"nobody said" is the one that publishes less.
"""

from __future__ import annotations

from datetime import date, timedelta

# lib/atc_updates.py's trail extent, for the same reason it records: a mile
# outside the trail is not a location, it is a mistake with a decimal point.
TRAIL_MILE_MIN = 0.0
TRAIL_MILE_MAX = 2197.5

STATUSES = ("upcoming", "completed", "cancelled")

# Phase B is read-only, so `contact` is the only mode a reviewed row may
# carry today: `in_app` means an RSVP the backend accepts, which is Phase D
# (#762), and a row claiming it before the endpoint exists would render a
# button that files nothing.
SIGNUP_MODES = ("contact",)

REQUIRED_FIELDS = ("id", "club_name", "title", "starts_on", "ends_on", "signup_mode")


def _date_problem(row: dict, field: str) -> str | None:
    value = row.get(field)
    if not isinstance(value, str):
        return f"{field} must be a YYYY-MM-DD string"
    try:
        date.fromisoformat(value)
    except ValueError:
        return f"{field} is not a date: {value!r}"
    return None


def row_problems(row: dict) -> list[str]:
    """Everything wrong with one row, or empty. Whole sentences, because the
    person reading them is editing a JSON file by hand."""
    problems: list[str] = []
    row_id = row.get("id", "<no id>")

    for field in REQUIRED_FIELDS:
        if field not in row or row.get(field) in ("", None):
            problems.append(f"{row_id}: {field} is required")

    for field in ("starts_on", "ends_on"):
        if isinstance(row.get(field), str):
            problem = _date_problem(row, field)
            if problem is not None:
                problems.append(f"{row_id}: {problem}")

    if not problems and date.fromisoformat(row["ends_on"]) < date.fromisoformat(row["starts_on"]):
        problems.append(f"{row_id}: ends_on is before starts_on")

    if row.get("status", "upcoming") not in STATUSES:
        problems.append(f"{row_id}: status must be one of {STATUSES}")

    if row.get("signup_mode") not in SIGNUP_MODES:
        problems.append(f"{row_id}: signup_mode must be one of {SIGNUP_MODES} - `in_app` arrives with the signup backend (#762)")
    if row.get("signup_mode") == "contact" and not isinstance(row.get("signup_contact"), str):
        problems.append(f"{row_id}: a contact-mode row needs signup_contact (a mailto: or tel: or https: string)")

    # A workday somebody might travel to needs a place: coordinates, or a
    # mile the client can put on the centerline, or both.
    has_coords = isinstance(row.get("lat"), (int, float)) and isinstance(row.get("lon"), (int, float))
    has_mile = isinstance(row.get("mile"), (int, float))
    if not has_coords and not has_mile:
        problems.append(f"{row_id}: a row needs lat+lon, or a mile, or both - a workday with no place sends nobody anywhere")
    if has_mile and not (TRAIL_MILE_MIN <= float(row["mile"]) <= TRAIL_MILE_MAX):
        problems.append(f"{row_id}: mile {row['mile']} is off the trail's own extent ({TRAIL_MILE_MIN}-{TRAIL_MILE_MAX})")

    capacity = row.get("capacity")
    if capacity is not None and (not isinstance(capacity, int) or capacity < 1):
        problems.append(f"{row_id}: capacity is a positive whole number of people, or absent for 'no cap stated'")

    return problems


def _sample_row_problems(row: dict) -> list[str]:
    """Sample rows swap absolute dates for relative ones and must say they
    are samples out loud - a UA tester reading `[Sample]` cannot mistake the
    row for a real club's ask."""
    problems: list[str] = []
    row_id = row.get("id", "<no sample id>")

    if not isinstance(row.get("starts_in_days"), int) or not isinstance(row.get("ends_in_days"), int):
        problems.append(f"{row_id}: sample rows carry starts_in_days/ends_in_days (whole days from bake time)")
    elif row["ends_in_days"] < row["starts_in_days"]:
        problems.append(f"{row_id}: ends_in_days is before starts_in_days")

    if not str(row.get("title", "")).startswith("[Sample]"):
        problems.append(f"{row_id}: a sample row's title starts with '[Sample]', so nothing downstream can drop the label")

    checked = {**row, "starts_on": "2026-01-01", "ends_on": "2026-01-01"}
    checked.pop("starts_in_days", None)
    checked.pop("ends_in_days", None)
    problems.extend(row_problems(checked))
    return problems


def file_problems(document: dict) -> list[str]:
    """Everything wrong with the reviewed file, or empty. One bad row fails
    the whole file - lib/atc_updates.py's stance, for its reason: a partial
    set is worse than none because the gap is invisible."""
    problems: list[str] = []

    rows = document.get("rows")
    if not isinstance(rows, list):
        problems.append("rows must be a list (empty is fine - that is production's honest state today)")
        rows = []
    samples = document.get("ua_sample_rows", [])
    if not isinstance(samples, list):
        problems.append("ua_sample_rows must be a list")
        samples = []

    seen: set[str] = set()
    for row in [*rows, *samples]:
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id in seen:
            problems.append(f"{row_id}: duplicate id - the client keys and dedupes on it")
        if isinstance(row_id, str):
            seen.add(row_id)

    for row in rows:
        problems.extend(row_problems(row))
    for row in samples:
        problems.extend(_sample_row_problems(row))

    return problems


def is_reviewed(document: dict) -> bool:
    """Unreviewed publishes nothing - the same gate as the ATC file, for the
    same reason: a merged pull request over a reviewed date is what releases
    rows, never a bake finding a file."""
    reviewed = document.get("reviewed_at")
    if not isinstance(reviewed, str) or reviewed.strip() == "":
        return False
    try:
        date.fromisoformat(reviewed[:10])
    except ValueError:
        return False
    return True


def _resolved_sample(row: dict, today: date) -> dict:
    resolved = {key: value for key, value in row.items() if key not in ("starts_in_days", "ends_in_days")}
    resolved["starts_on"] = (today + timedelta(days=row["starts_in_days"])).isoformat()
    resolved["ends_on"] = (today + timedelta(days=row["ends_in_days"])).isoformat()
    return resolved


def published_rows(document: dict, *, environment: str | None, today: date) -> list[dict]:
    """The rows one environment's artifact carries.

    Production - and an UNSET environment, read conservatively - gets `rows`
    alone. UA and dev get the samples too, with their relative dates resolved
    against bake time so the fourteen-day window always has something in it
    to rehearse against. `status` defaults to `upcoming` on the way out so
    the client never meets an absent field.
    """
    rows = [dict(row) for row in document.get("rows", [])]
    if environment in ("ua", "dev"):
        rows.extend(_resolved_sample(row, today) for row in document.get("ua_sample_rows", []))
    for row in rows:
        row.setdefault("status", "upcoming")
        row.setdefault("capacity", None)
        row.setdefault("description", None)
        row.setdefault("lat", None)
        row.setdefault("lon", None)
        row.setdefault("mile", None)
    return rows
