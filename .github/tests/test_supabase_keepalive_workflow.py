"""Tests that exactly one scheduled workflow keeps the Supabase project awake.

The job itself is tested in backend/tests/test_supabase_keepalive.py, which is
where its judgement lives. What is left over is a claim about the *set* of
workflows, which no single workflow can make about itself:

**Only one of them should be doing this.** A free-plan project pauses on
insufficient database activity, and one weekly sweep answers that. A second
scheduled workflow reaching the same project would add no protection - the
project is either getting activity or it is not - while adding a second thing
to keep in sync, a second place for a stale key to hide, and a second run to
wonder about when one of them goes red. This fails when one appears, which is
the only moment the duplication is cheap to undo.

**And it should really be weekly, on Sunday.** The schedule is the one part of
this job with no feedback loop: a cron expression that quietly means "the first
of the month" or "only in July" produces a workflow that looks configured, runs
green when it runs, and lets the project pause anyway. Nothing else would
notice until the pause email.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / "workflows"
KEEPALIVE = "supabase-keepalive.yml"

# The settings that name the project. A workflow reading either of these is
# talking to Supabase; nothing else in this repository does.
SUPABASE_REFERENCE = re.compile(r"\b(?:secrets|vars)\.SUPABASE_[A-Z_]+", re.IGNORECASE)

SUNDAY = {"0", "7", "sun"}


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


def _workflows():
    parsed = {}
    for path in sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml")):
        parsed[path.name] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parsed


def _scheduled_supabase_workflows():
    return sorted(
        name
        for name, parsed in _workflows().items()
        if _crons(parsed) and any(SUPABASE_REFERENCE.search(text) for text in _strings(parsed))
    )


def test_exactly_one_scheduled_workflow_reaches_the_supabase_project():
    found = _scheduled_supabase_workflows()

    assert found == [KEEPALIVE], (
        "A free-plan Supabase project needs one scheduled job keeping it awake, and gains nothing from a second. "
        f"Scheduled workflows reaching the project: {found or 'none'}. If the new one replaces "
        f"{KEEPALIVE}, delete that file and its tests rather than running both."
    )


def test_the_keepalive_runs_weekly_on_sunday():
    crons = _crons(_workflows()[KEEPALIVE])

    assert len(crons) == 1, f"{KEEPALIVE} should carry exactly one schedule, found {crons}"

    minute, hour, day_of_month, month, day_of_week = crons[0].split()

    assert day_of_week.lower() in SUNDAY, f"{KEEPALIVE} should run on Sunday, its day-of-week field is {day_of_week!r}"
    assert day_of_month == "*", f"{KEEPALIVE} would only run on some Sundays - its day-of-month field is {day_of_month!r}"
    assert month == "*", f"{KEEPALIVE} would only run in some months - its month field is {month!r}"
    # A wildcard in either of these turns one weekly run into 24 or 1440 of
    # them, which is a different job than the one that was reviewed.
    assert minute.isdigit(), f"{KEEPALIVE} would run every minute of its hour - its minute field is {minute!r}"
    assert hour.isdigit(), f"{KEEPALIVE} would run every hour of its day - its hour field is {hour!r}"


def test_the_keepalive_can_also_be_run_by_hand():
    # The schedule cannot be tested by waiting a week, and the run somebody
    # actually needs is the one right after a pause warning email.
    assert "workflow_dispatch" in _triggers(_workflows()[KEEPALIVE])
