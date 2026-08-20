"""Tests that exactly one scheduled workflow keeps the Supabase project awake,
often enough to matter.

The job itself is tested in backend/tests/test_supabase_keepalive.py, which is
where its judgement lives. What is left over is a claim about the *set* of
workflows, which no single workflow can make about itself:

**Only one of them should be doing this.** A free-plan project pauses on
insufficient database activity, and one keepalive answers that. A second
scheduled workflow reaching the same project would add no protection - the
project is either getting activity or it is not - while adding a second thing
to keep in sync, a second place for a stale key to hide, and a second run to
wonder about when one of them goes red. This fails when one appears, which is
the only moment the duplication is cheap to undo.

**And it should run often enough.** The schedule is the one part of this job
with no feedback loop: a cron expression that quietly means "the first of the
month" or "only in July" produces a workflow that looks configured, runs green
when it runs, and lets the project pause anyway. Nothing else would notice
until the pause email.

So the schedule is judged on the **longest gap it leaves**, not on the string
it is written as. `50 */20 * * *` reads like "every 20 hours" and is not -
cron's hour field repeats within the day, so it fires at 00:50 and 20:50, with
gaps of 20 hours and then 4. The 20 is the number that matters, and a test
asserting the string would have said nothing about it while breaking on every
harmless re-spelling.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / "workflows"
KEEPALIVE = "supabase-keepalive.yml"

# The settings that name the project. This used to end "nothing else in this
# repository does", and that was false the day schema-drift.yml shipped
# (#656): the project's DATABASES are also reachable through secrets named
# for their own jobs - the migration pooler URLs, the conditions reader -
# each engineered precisely so this pattern would not read it as a second
# keepalive. Both roads are counted now; the roster test below is the census.
SUPABASE_REFERENCE = re.compile(r"\b(?:secrets|vars)\.SUPABASE_[A-Z_]+", re.IGNORECASE)

# The other road into the same project: connection strings for its Postgres,
# named for the job that holds them rather than for Supabase.
DATABASE_SECRET = re.compile(r"\bsecrets\.[A-Z_]*DATABASE_URL\b")

# Supabase's guidance is "a few user requests to the database each day over the
# previous week" - a per-day measure. A gap this size keeps at least one run in
# every calendar day and leaves room for a run that fails or is queued late.
LONGEST_ACCEPTABLE_GAP_HOURS = 20


def _strings(node):
    """Every string anywhere in a parsed workflow, keys included.

    Parsing rather than scanning raw text, for the reason
    test_repository_settings.py gives: a comment mentioning `vars.SUPABASE_URL`
    is not a workflow that reads it, and this file's own header would otherwise
    make every workflow look like it talked to Supabase.
    """
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(key)
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)


def _triggers(parsed):
    """A workflow's `on:` block.

    YAML 1.1 resolves a bare `on` to the boolean True, which is why this cannot
    simply be `parsed["on"]` - and why a test that got it wrong would find no
    schedules anywhere and pass for the wrong reason.
    """
    return parsed.get(True, parsed.get("on")) or {}


def _crons(parsed):
    schedule = _triggers(parsed).get("schedule") or []
    return [entry["cron"] for entry in schedule if isinstance(entry, dict) and "cron" in entry]


def _field(expression: str, low: int, high: int) -> set[int]:
    """Expand one cron field into the values it fires on.

    Enough of the syntax to judge a schedule honestly - `*`, `*/n`, `a-b`,
    `a-b/n`, comma lists and bare numbers. A field this cannot parse raises,
    which is the right outcome: an unreadable schedule must not quietly pass a
    test whose whole job is reading it.
    """
    values: set[int] = set()
    for part in expression.split(","):
        step = 1
        if "/" in part:
            part, _, raw_step = part.partition("/")
            step = int(raw_step)
        if part == "*":
            start, end = low, high
        elif "-" in part:
            raw_start, _, raw_end = part.partition("-")
            start, end = int(raw_start), int(raw_end)
        else:
            start = end = int(part)
        values.update(range(start, end + 1, step))
    return values


def _longest_gap_hours(cron: str) -> float:
    """The longest stretch, in hours, this expression leaves with no run.

    Measured across one day and wrapping around midnight, which is what makes
    `50 */20 * * *` come out at 20 rather than at the 4 its second gap
    suggests.
    """
    minute, hour, day_of_month, month, day_of_week = cron.split()

    # A schedule that skips days cannot be reasoned about hour by hour, and is
    # not something this job should ever have.
    assert day_of_month == "*", f"{KEEPALIVE} would only run on some days of the month - {day_of_month!r}"
    assert month == "*", f"{KEEPALIVE} would only run in some months - {month!r}"
    assert day_of_week == "*", f"{KEEPALIVE} would only run on some days of the week - {day_of_week!r}"

    minutes = sorted(h * 60 + m for h in _field(hour, 0, 23) for m in _field(minute, 0, 59))
    assert minutes, f"{KEEPALIVE} has a schedule that never fires - {cron!r}"

    # Wrap: the gap from the last run of one day to the first of the next.
    gaps = [b - a for a, b in zip(minutes, minutes[1:])] + [minutes[0] + 24 * 60 - minutes[-1]]
    return max(gaps) / 60


def _workflows():
    parsed = {}
    for path in sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml")):
        parsed[path.name] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parsed


def _scheduled_supabase_workflows():
    return sorted(
        name
        for name, parsed in _workflows().items()
        if _crons(parsed) and any(SUPABASE_REFERENCE.search(text) or DATABASE_SECRET.search(text) for text in _strings(parsed))
    )


# Every scheduled road into the Supabase project, and why each is deliberate.
# Joining this roster is a conscious act with a reason, made at the moment a
# new entrant is cheap to reconsider - which is the enforcement the old
# "exactly one" census claimed and could not deliver (#656).
SCHEDULED_ROSTER = {
    KEEPALIVE: "the keepalive itself - PostgREST reads, the database activity Supabase measures",
    "publish-conditions.yml": "bakes verified closures and reports daily, through the conditions reader credentials",
    "schema-drift.yml": "reads both databases' schemas daily through the migration pooler URLs; deliberately not a "
    "keepalive (its SUPABASE_URL is a placeholder), but scheduled database activity all the same",
    "check-auth-redirects.yml": "GET /auth/v1/verify daily (#488) - GoTrue queries its own auth schema tables to "
    "reject the junk token, which is real database activity even though the point of the probe is the redirect "
    "allow-list, not keeping the project awake",
}


def test_every_scheduled_road_to_the_supabase_project_is_on_the_roster():
    """The keepalive question is "does the project get scheduled activity
    from one place or several" - and the census used to measure only the
    SUPABASE_* settings, a weaker property its own name overclaimed (#656).
    Two scheduled workflows reach the same project's databases through
    secrets named for their own jobs, each written to slip past the old
    pattern, so the dodge was becoming the house style. Both roads are
    counted now, against a roster that names each member's reason; a fourth
    entrant fails here by name."""
    found = _scheduled_supabase_workflows()

    assert found == sorted(SCHEDULED_ROSTER), (
        "The scheduled workflows reaching the Supabase project are not the ones the roster names. "
        f"Found: {found or 'none'}; roster: {sorted(SCHEDULED_ROSTER)}. A new scheduled road to the project is a "
        "second thing to keep in sync and a second load profile - join the roster with a stated reason, or reach "
        "the project some other way. If it replaces a member, remove that member and its tests rather than running "
        "both."
    )


def test_the_project_is_never_left_untouched_for_longer_than_the_gap_allows():
    crons = _crons(_workflows()[KEEPALIVE])

    assert len(crons) == 1, f"{KEEPALIVE} should carry exactly one schedule, found {crons}"

    gap = _longest_gap_hours(crons[0])

    assert gap <= LONGEST_ACCEPTABLE_GAP_HOURS, (
        f"{KEEPALIVE} leaves {gap:g} hours with no run ({crons[0]!r}). Supabase measures database activity per day, "
        f"so the longest gap is the number that decides whether this job works - keep it to "
        f"{LONGEST_ACCEPTABLE_GAP_HOURS} hours or less."
    )


def test_the_gap_is_measured_across_midnight_rather_than_within_the_day():
    # The bug this test exists to prevent is in the test, not the workflow: a
    # gap calculation that stops at the end of the day reports 4 hours for the
    # real schedule and would wave through one that fires twice at breakfast
    # and never again.
    assert _longest_gap_hours("50 */20 * * *") == 20
    assert _longest_gap_hours("0 6,10 * * *") == 20
    assert _longest_gap_hours("0 */6 * * *") == 6
    assert _longest_gap_hours("30 7 * * *") == 24


def test_the_keepalive_can_also_be_run_by_hand():
    # The schedule cannot be tested by waiting, and the run somebody actually
    # needs is the one right after a pause warning email.
    assert "workflow_dispatch" in _triggers(_workflows()[KEEPALIVE])
