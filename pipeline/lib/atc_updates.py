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

from datetime import date, datetime, timezone
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

# ATC's own categories, as published on their Trail Updates page. A closed
# set: a category this does not know is a page ATC has changed the shape of,
# which is a thing to look at rather than to pass through to a hiker as an
# unrecognised word.
#
# `Animal` was not in the five measured on 2026-08-09 and was carrying two
# live bear warnings on 2026-08-12. That is this list working rather than
# failing - the reviewer met a refusal, looked, and added a word ATC had
# started using. It is the cheap version of the cost
# features/ATC_TRAIL_UPDATES.md names as "their HTML is not an API".
#
# THE SECOND ROW BELOW IS THE SAME LESSON AT SIX TIMES THE SIZE. Reviewing
# all ten pages of ATC's listing on 2026-08-24 (#945) read a category off
# every one of the 89 updates live that day, and six words appeared that the
# six above do not cover. Counts are of those 89:
#
#     Water         4    closed wells, a shelter's spigot off
#     Relocation    1    a side trail moved
#     Permits       1    the Smokies' backcountry permit system
#     Construction  1    the Bear Mtn Bridge deck replacement
#     Fire          1    Roan Mountain's burn ban, renewed to 2030
#     Conservation  1    a camping restriction in a Special Biological Area
#
# None of these is exotic and two of them - `Water` and `Fire` - sit directly
# on the paths features/../CLAUDE.md calls the ways this app can hurt
# somebody. They were invisible for as long as the review only read page one,
# which is the actual finding of #945 rather than the count of updates.
CATEGORIES = frozenset(
    {
        "Detour",
        "Alert",
        "Closure",
        "Parking",
        "Hiking Safety",
        "Animal",
        "Water",
        "Relocation",
        "Permits",
        "Construction",
        "Fire",
        "Conservation",
    }
)

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
    "obstructs_trail",
    "updated_at",
    "source_url",
)

#: Provenance, carried into the artifact so a display cannot outrun its
#: source (CLAUDE.md). `reviewed` means a person read ATC's page and typed the
#: row; `unreviewed` means this build parsed it off their site an hour ago and
#: nobody has checked it. Those are different claims and the app has to be
#: able to tell a hiker which one it is holding.
REVIEWED = "reviewed"
UNREVIEWED = "unreviewed"
REVIEW_STATES = frozenset({REVIEWED, UNREVIEWED})

PUBLISHED_FIELDS = (*REQUIRED_FIELDS, "review_state")


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

    # Required as a real boolean rather than defaulted, because the default
    # would be a guess about whether a hiker can walk through, and ATC's own
    # category cannot answer it. Measured against their live page on
    # 2026-08-12: the only notice filed as `Closure` is a closed SHELTER, with
    # the trail past it open, while the one thing that genuinely stops a hiker
    # - the Harpers Ferry footbridge - is filed as `Detour`. A rule reading
    # the category would be wrong in both directions at once.
    if "obstructs_trail" in row and not isinstance(row.get("obstructs_trail"), bool):
        problems.append(
            "obstructs_trail must be true or false - whether a hiker is stopped from walking "
            "through, which is not the same question as ATC's category (a closed shelter is a "
            "`Closure` and leaves the trail open)"
        )

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
    return [
        {field: (REVIEWED if field == "review_state" else row[field]) for field in PUBLISHED_FIELDS}
        for row in document["updates"]
    ]


# WHY THERE IS NO ALL-CLEAR REFUSAL HERE ANY MORE.
#
# There was one: a list of words - "reopened", "is complete", "has been
# lifted" - that refused any update whose latest edit might be announcing the
# END of the thing it warned about. #463's worry, and a fair one: an ingest
# that only ever adds notices accumulates barriers across trail people have
# been walking.
#
# It was removed on 2026-08-24 because it was wrong about live notices more
# often than it was right about dead ones. Measured against the 22 updates ATC
# had edited in the previous 90 days, it refused two, and BOTH were current:
# the Andy Layne relocation, whose "is complete" sits above a live road-walk
# on a road ATC says has "little to no shoulder", and Max Patch, whose "has
# been completed" is about restoration work inside a camping closure that runs
# to June 2029. Meanwhile the VA Creeper closure - nine miles of A.T. shut
# until March 2027 - says "will reopen", and would have been refused for it.
#
# What makes that safe to drop is that the two things #463 feared cannot
# happen here. An automatic row carries ATC's own headline verbatim, so an
# all-clear publishes AS an all-clear - "NC/TN: Iron Mtn Gap Reopened" reads
# as exactly what it is - and `auto_row` forces `obstructs_trail` false, so
# none of them can draw a barrier whatever the words say.


def _modified_after(date_modified: str, reviewed_at: str) -> bool:
    """Whether ATC edited this after the day a person last read their page."""
    try:
        edited = datetime.fromisoformat(date_modified)
    except ValueError:
        return False
    if edited.tzinfo is not None:
        edited = edited.astimezone(timezone.utc)
    try:
        looked = date.fromisoformat(reviewed_at[:10])
    except ValueError:
        return False
    return edited.date() > looked


def auto_publish_refusal(parsed, reviewed_ids: frozenset[str] | set[str], reviewed_at: str) -> str | None:
    """Why this parsed update may NOT be published without a person, or None.

    THE GATE #963 IS BUILT AROUND, and it is deliberately narrow. Everything
    it lets through has exactly one reading; everything with two readings is
    somebody's judgement and waits for one.

    THE RECENCY RULE IS THE LOAD-BEARING ONE, and it was not in #963's
    original description - it is there because the gate was run against ATC's
    real 89 updates before any of this shipped, and without it the gate
    published almost exactly the set a person had just decided to leave out.

    That is structural rather than bad luck. After a review, everything still
    unreviewed IS the reviewer's reject pile: they read all 89 and kept 35, so
    "publish what is not reviewed and parses cleanly" is a rule that publishes
    rejects. Measured 2026-08-24, without this rule the gate let through 22
    rows - twelve bear incidents from 2024 and 2025, a hunting season its own
    text ends on 2025-12-31, four vehicle break-ins, and a duplicate of a
    closure already carried.

    So an update auto-publishes only when ATC edited it AFTER the day a person
    last read their page. Then the only thing it can ever add is something
    nobody has had the chance to judge - which is the actual gap #963 exists
    to close - and it can never overturn a reviewer's decision, because every
    decision they made is about a page older than their own review date.

    Strictly after, not on-or-after: an edit landing the same day a reviewer
    worked may or may not have been seen, and the cost of waiting a day is a
    notice arriving late, against the cost of the other direction, which is
    silently republishing something a person removed on purpose.

    Returns the reason rather than a bool so the job can say what it skipped
    and why - a silent cap reads as "covered everything" when it did not.
    """
    if parsed.slug in reviewed_ids:
        # A person's row always wins. They may have given it a band, a
        # corrected mile, or decided it should not be here at all, and none of
        # those survives being overwritten by a parse.
        return "already reviewed by a person"

    if not parsed.date_modified:
        return "no dateModified on the page"
    if not _modified_after(parsed.date_modified, reviewed_at):
        return f"last edited {parsed.date_modified[:10]}, not since the review on {reviewed_at}"
    if not parsed.title or not parsed.title.strip():
        return "no title"
    if parsed.category not in CATEGORIES:
        # A word this build does not know means ATC changed the shape of their
        # page, which is a thing to look at rather than to pass through.
        return f"category {parsed.category!r} is not one this build knows"
    if not parsed.states:
        return "no states on the page"

    reference = agreed_mile(parsed.miles)
    if reference is None:
        # NOT "the first one wins". Iron Mtn Gap states five ranges
        # accumulated over months of edits and the current one is not
        # mechanically distinguishable from its own history (#463). Zero is
        # the region-wide advisory that has no place on a map at all.
        return f"{len(parsed.miles)} mile references that do not agree on one place"
    ends = [reference.start] + ([reference.end] if reference.end is not None else [])
    if any(end is None or not TRAIL_MILE_MIN <= end <= TRAIL_MILE_MAX for end in ends):
        # The thousands-separator failure, caught rather than published: a
        # mile off the end of the trail is a mistake with a decimal point in
        # it, not a place.
        return f"{reference.raw!r} is outside the trail's own extent"
    if reference.end is not None and reference.end < reference.start:
        return f"{reference.raw!r} runs backwards"

    return None


def agreed_mile(miles: list):
    """The one span every mile reference on the page agrees on, or None.

    REPEATING A MILE IS NOT AMBIGUITY, and the rule this replaced could not
    tell the difference. ATC restates a location as they edit a notice, so
    "exactly one reference" refused pages that name the same spot twice: the
    Harpers Ferry footbridge closure carries `NOBO mile 1,026.7` in both its
    2026 and 2025 sections and was held back as though the two disagreed.

    Genuine disagreement still refuses. When a notice names several DIFFERENT
    places - Iron Mtn Gap's five ranges, accumulated over months of edits -
    there is no way to tell the current one from its own history, and picking
    is a coin toss with a hiker's location.
    """
    if not miles:
        return None
    spans = {(m.start, m.end) for m in miles}
    return miles[0] if len(spans) == 1 else None


def _as_utc_stamp(iso: str) -> str:
    """ATC's `dateModified` in the `...Z` form every reviewed row already uses.

    Their JSON-LD carries a local offset (`2026-08-19T16:22:50-04:00`). A
    reviewed row carries UTC, because a person converted it by hand. Two
    spellings of the same instant in one artifact would make `updated_at`
    sortable only by accident, so the parse converts rather than passing the
    offset through.
    """
    try:
        stamped = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=timezone.utc)
    return stamped.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def auto_row(parsed) -> dict:
    """One parsed update as a publishable row, with the rails bolted on.

    `obstructs_trail` IS FORCED FALSE AND IS NOT READ FROM ANYTHING. It is the
    one field that decides whether a band is drawn across the treadway, and
    `lib/atc_updates.py`'s own measurements say ATC's category cannot answer
    it - their only `Closure` on 2026-08-12 was a shelter with open trail past
    it, while the Harpers Ferry footbridge, which genuinely stops a hiker, is
    filed `Detour`. So an unreviewed row gets a dot and a banner and can never
    get a barrier. Upgrading it to one is what review is for.
    """
    reference = agreed_mile(parsed.miles)
    return {
        "atc_id": parsed.slug,
        "title": parsed.title.strip(),
        "category": parsed.category,
        "states": list(parsed.states),
        "start_mile_marker": reference.start,
        "end_mile_marker": reference.end if reference.end is not None else reference.start,
        "obstructs_trail": False,
        "updated_at": _as_utc_stamp(parsed.date_modified),
        "source_url": parsed.source_url,
        "review_state": UNREVIEWED,
    }
