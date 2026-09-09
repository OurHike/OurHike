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

NO INVENTED WORKDAY MAY REACH A HIKER, IN ANY ENVIRONMENT. A person driving
to a trailhead for an event nobody scheduled is this feature's own failure
mode, self-inflicted - so the reviewed file's `rows` are the whole published
set, and they stay empty until a real club supplies real workdays.

That rule used to stop at production. Between 2026-08-20 and 2026-09-09 the
reviewed file also carried `ua_sample_rows`: two '[Sample]' workdays that
published to UA and dev so the mechanism was rehearsable end to end, and
this module resolved their relative dates against bake time. Maintainer
decision 2026-09-09 removed them - a UA tester reading a map is reading a
map, and a '[Sample]' label was the only thing separating an invented pin
from a real one. `file_problems` now REFUSES the key rather than ignoring it, so
re-adding samples fails the bake instead of quietly publishing them again;
that refusal is the mechanism, and this paragraph is why it exists.

What it costs: nothing exercises the workday path against a live bucket any
more. The suites cover it against fixtures, and the first real club row will
cover it for real.
"""

from __future__ import annotations

from datetime import date

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


def file_problems(document: dict) -> list[str]:
    """Everything wrong with the reviewed file, or empty. One bad row fails
    the whole file - lib/atc_updates.py's stance, for its reason: a partial
    set is worse than none because the gap is invisible."""
    problems: list[str] = []

    rows = document.get("rows")
    if not isinstance(rows, list):
        problems.append("rows must be a list (empty is fine - that is the file's honest state today)")
        rows = []

    # The retired sample list, refused rather than ignored. Ignoring it would
    # make re-adding samples a silent no-op that reads like it worked; this
    # way the bake stops and says which rule it stopped for. See the module
    # docstring for the decision.
    if "ua_sample_rows" in document:
        problems.append(
            "ua_sample_rows is retired (maintainer decision 2026-09-09): no invented workday may reach a hiker "
            "in ANY environment, so `rows` is the only list. Move a real club's row into `rows`, or delete the key"
        )

    seen: set[str] = set()
    for row in rows:
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id in seen:
            problems.append(f"{row_id}: duplicate id - the client keys and dedupes on it")
        if isinstance(row_id, str):
            seen.add(row_id)

    for row in rows:
        problems.extend(row_problems(row))

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


def published_rows(document: dict) -> list[dict]:
    """The rows the artifact carries - `rows`, everywhere, and nothing else.

    Every environment gets the same list, which is the whole point of the
    2026-09-09 decision in the module docstring: there is no longer a copy of
    this artifact anywhere that carries a workday nobody scheduled. `status`
    defaults to `upcoming` on the way out so the client never meets an absent
    field.
    """
    rows = [dict(row) for row in document.get("rows", [])]
    for row in rows:
        row.setdefault("status", "upcoming")
        row.setdefault("capacity", None)
        row.setdefault("description", None)
        row.setdefault("lat", None)
        row.setdefault("lon", None)
        row.setdefault("mile", None)
    return rows
