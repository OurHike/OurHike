"""The shape of a reviewed ATC Trail Update, and what makes one publishable.

features/ATC_TRAIL_UPDATES.md is the design; this is the half a test can run.
It owns one question - **is this row safe to put in front of a hiker?** - and
answers it for the reviewed file (`reference/atc_updates.json`) before
`export_atc_updates.py` bakes anything.

WHY VALIDATION IS THE INTERESTING PART HERE, when the same rows in the
closures table are validated by a database. Because there is no database. ATC
updates deliberately never reach `public.closures` - `reported_by` is
`nullable=False` and an ATC notice has no reporter, and the synthetic-profile
workaround is refused by the design - so the reviewed file is edited by hand
and the only thing between a typo and a hiker is this module.

The failure that matters is a **confident wrong answer**, and it is not
hypothetical: `spike_atc_updates.py` records the near-miss where a number
pattern without the thousands separator reads `NOBO mile 1,503.6` as mile 1,
putting a Connecticut shelter in Georgia. It parses. It looks plausible. It
is 1,502 miles wrong. So the checks below are mostly about *placement being
possible at all* rather than about JSON being well-formed - a mile outside
the trail's own extent is not a location, it is a mistake with a decimal
point in it.

ONE BAD ROW FAILS THE WHOLE FILE, matching export_conditions.py's stance for
the same reason: a partial set of safety notices is worse than none, because
the gap is invisible. A hiker cannot tell a closure that was dropped from a
stretch of trail that is open.
"""

from __future__ import annotations

from urllib.parse import urlparse

# The trail's own extent, from ATC's half-mile marker layer: 4,395 points,
# `Measure` running 0.5 to 2197.5. Measured against the live service on
# 2026-08-09 and repeated from spike_atc_updates.py rather than imported,
# because a spike is deliberately not a dependency of anything that ships.
#
# A parsed mile outside this is not a location. Checking it is what turns the
# thousands-separator bug from "a shelter drawn in the wrong state" into "the
# bake refused to run", and only one of those reaches a hiker.
TRAIL_MILE_MIN = 0.5
TRAIL_MILE_MAX = 2197.5

# ATC's own categories, as published on their Trail Updates page (measured
# 2026-08-09). A closed set: a category this does not know is a page ATC has
# changed the shape of, which is a thing to look at rather than to pass
# through to a hiker as an unrecognised word.
CATEGORIES = frozenset({"Detour", "Alert", "Closure", "Parking", "Hiking Safety"})

# Every field a published row carries. Facts and a link - deliberately not
# ATC's body text, which is theirs (features/ATC_TRAIL_UPDATES.md, and the
# `licence` field on this source in sources.json).
REQUIRED_FIELDS = (
    "atc_id",
    "title",
    "category",
    "states",
    "start_mile_marker",
    "end_mile_marker",
    "updated_at",
    "source_url",
)

PUBLISHED_FIELDS = REQUIRED_FIELDS


def _mile_problem(row: dict, field: str) -> str | None:
    value = row.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return f"{field} is {value!r}, which is not a mile"
    if not TRAIL_MILE_MIN <= float(value) <= TRAIL_MILE_MAX:
        return (
            f"{field} is {value}, outside the trail's own extent "
            f"({TRAIL_MILE_MIN}-{TRAIL_MILE_MAX}). A mile off the end of the trail is a "
            "mistake with a decimal point in it, not a place - see lib/atc_updates.py."
        )
    return None


def row_problems(row: dict) -> list[str]:
    """Everything wrong with one reviewed row, in the order it was checked.

    A list rather than the first failure, so that a person fixing the file
    sees the whole of what is wrong with a row in one run instead of peeling
    it one message at a time.
    """
    problems = []

    for field in REQUIRED_FIELDS:
        if field not in row:
            problems.append(f"missing {field}")

    atc_id = row.get("atc_id")
    if "atc_id" in row and (not isinstance(atc_id, str) or not atc_id.strip()):
        problems.append("atc_id is empty")

    title = row.get("title")
    if "title" in row and (not isinstance(title, str) or not title.strip()):
        problems.append("title is empty")

    category = row.get("category")
    if "category" in row and category not in CATEGORIES:
        problems.append(f"category {category!r} is not one ATC publishes ({', '.join(sorted(CATEGORIES))})")

    states = row.get("states")
    if "states" in row and (
        not isinstance(states, list) or not states or not all(isinstance(s, str) and s.strip() for s in states)
    ):
        problems.append("states must be a non-empty list of state codes")

    for field in ("start_mile_marker", "end_mile_marker"):
        if field in row:
            problem = _mile_problem(row, field)
            if problem:
                problems.append(problem)

    start, end = row.get("start_mile_marker"), row.get("end_mile_marker")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and not isinstance(start, bool):
        if end < start:
            # Not silently swapped. A reversed pair means the reviewer read
            # ATC's sentence backwards, and the range they meant is not
            # recoverable from the one they wrote - `closureSpanMiles` would
            # take the absolute value and draw a band that looks right while
            # having been entered wrong.
            problems.append(f"end_mile_marker {end} is before start_mile_marker {start}")

    updated_at = row.get("updated_at")
    if "updated_at" in row and (not isinstance(updated_at, str) or not updated_at.strip()):
        problems.append("updated_at is empty - it is ATC's own date and the one a hiker cares about")

    source_url = row.get("source_url")
    if "source_url" in row:
        scheme = urlparse(source_url).scheme if isinstance(source_url, str) else ""
        if scheme not in ("http", "https"):
            # The same rule chrome/ClosureSheet.tsx enforces on the way out,
            # applied on the way in. A safety sheet renders this as a link a
            # hiker taps, and `javascript:` is why that validation exists;
            # refusing it here means the client's guard is a second line
            # rather than the only one.
            problems.append(f"source_url {source_url!r} is not an http(s) URL")

    return problems


def file_problems(document: dict) -> list[str]:
    """Everything wrong with the reviewed file as a whole.

    Includes the rows, and the two things only the whole file can be wrong
    about: a duplicated `atc_id`, and a review that never happened.
    """
    problems = []

    updates = document.get("updates")
    if not isinstance(updates, list):
        return ["`updates` is missing or is not a list"]

    seen = set()
    for index, row in enumerate(updates):
        if not isinstance(row, dict):
            problems.append(f"update {index} is not an object")
            continue
        label = row.get("atc_id") or f"update {index}"
        problems.extend(f"{label}: {problem}" for problem in row_problems(row))

        atc_id = row.get("atc_id")
        if isinstance(atc_id, str) and atc_id in seen:
            # The id is how the client keys a band and how a reviewer finds
            # the row again. Two rows sharing one is a copy-paste that would
            # render as one update quietly replacing another.
            problems.append(f"{atc_id}: appears more than once")
        if isinstance(atc_id, str):
            seen.add(atc_id)

    return problems


def is_reviewed(document: dict) -> bool:
    """Whether a person has actually checked this file against ATC's page.

    The file exists from the moment the feature does, with no rows in it, and
    an unreviewed empty file and a reviewed empty one are different claims:
    the first says *nobody has looked*, the second says *we looked and ATC
    has nothing placeable*. Only the second is publishable, because only the
    second is true.

    `reviewed_at` is what separates them, and it is deliberately the reviewer's
    date rather than the bake's - see export_atc_updates.py for why a daily
    bake stamping a daily `generated_at` on a three-month-old review would be
    the dishonest version of this.
    """
    reviewed_at = document.get("reviewed_at")
    return isinstance(reviewed_at, str) and bool(reviewed_at.strip())


def published_rows(document: dict) -> list[dict]:
    """The rows as the artifact carries them: the published fields, in order.

    Projected rather than passed through, so that a note a reviewer left
    themselves in the file - or ATC body text somebody pasted in while
    working - cannot reach the bucket by accident. What ships is the field
    list this module names and nothing else.
    """
    return [{field: row[field] for field in PUBLISHED_FIELDS} for row in document["updates"]]
