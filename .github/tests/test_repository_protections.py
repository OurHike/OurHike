"""Tests that this repository's protections are what RELEASING.md §8 says.

The companion to test_repository_settings.py, and split the same way for the
same reason.

**What a checkout can answer** - whether `.github/expected-protections.yml`
still agrees with `.github/workflows/`. Runs anywhere, needs access to
nothing, and is the half with teeth day to day: workflows change, and a check
declared required whose workflow has quietly lost its `merge_group:` trigger
is a merge queue that hangs rather than fails.

**What only a live run can answer** - whether GitHub is actually configured
that way. `protections-check.yml` reads the API and hands the result here
through the environment. Unlike the settings check there is no secret to be
careful about: branch protection, environments and labels are configuration,
not credentials, so this file can print what it found.

**Why the asymmetry with #375 matters.** Making these settings is a human
action - no API this repository can reach will do it, which is why #375 is
open at all. What is automatable is noticing, and noticing is the difference
between a gate that was true the day it was configured and one that is true
now.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / ".github" / "expected-protections.yml"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

MANIFEST = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))

REQUIRED = MANIFEST["required_status_checks"]
NEVER_REQUIRED = MANIFEST["never_required"]
BRANCH = MANIFEST["branch"]


def _workflow(name: str):
    path = WORKFLOW_DIR / name
    assert path.exists(), f"expected-protections.yml names {name}, which does not exist in .github/workflows/"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(parsed) -> set[str]:
    """The events a workflow runs on.

    PyYAML parses a bare `on:` key as the boolean True, not the string "on" -
    the YAML 1.1 legacy every workflow file walks into. Both are checked
    because a file quoting it would otherwise look like a workflow with no
    triggers at all.
    """
    on = parsed.get(True, parsed.get("on"))
    if isinstance(on, dict):
        return set(on)
    if isinstance(on, list):
        return set(on)
    return {on} if on else set()


def _check_names(parsed) -> set[str]:
    """What GitHub will call each job's status check.

    A job's `name:` where it has one, its job id otherwise. This is the string
    the branch protection setting has to match, and getting it wrong produces
    a required check that never reports - which blocks every pull request
    rather than failing one.
    """
    names = set()
    for job_id, job in (parsed.get("jobs") or {}).items():
        names.add(job.get("name") or job_id if isinstance(job, dict) else job_id)
    return names


def _live(variable):
    raw = os.environ.get(variable)
    if not raw:
        return None
    return json.loads(raw)


LIVE = _live("LIVE_PROTECTIONS")

live = pytest.mark.skipif(
    LIVE is None,
    reason="Only a job with repository administration access can see how GitHub is configured - see protections-check.yml.",
)


# --- What a checkout can answer -------------------------------------------


def test_the_manifest_gives_a_reason_for_everything_it_declares():
    missing = [
        f"{section}.{name}"
        for section, entries in (
            ("required_status_checks", REQUIRED),
            ("never_required", NEVER_REQUIRED),
            ("settings", MANIFEST["settings"]),
            ("environments", MANIFEST["environments"]),
            ("labels", MANIFEST["labels"]),
        )
        for name, spec in entries.items()
        if not str((spec or {}).get("why", "")).strip()
    ]
    assert not missing, "expected-protections.yml entries with no `why` - what breaks when it is missing:\n  " + "\n  ".join(
        missing
    )


def test_every_required_check_can_report_on_a_merge_queue_entry():
    """The one that matters most, and the reason this file exists.

    BRANCHING.md: a workflow with no `merge_group:` trigger never reports
    against a queue entry, and that **hangs** the entry until the queue times
    out and ejects the pull request rather than failing it. So a check is only
    safe to require if its workflow carries that trigger - a fact about a file
    in this repository, which makes it checkable here instead of discoverable
    in production months after someone ticked a box.
    """
    hangs = []
    for check, spec in sorted(REQUIRED.items()):
        if "merge_group" not in _triggers(_workflow(spec["workflow"])):
            hangs.append(f"{check} (from {spec['workflow']})")
    assert not hangs, (
        "These checks are declared as required status checks, but their workflows do not trigger on `merge_group`. "
        "A required check that cannot report on a queue entry hangs it until the queue ejects the pull request - it "
        "does not fail it, so the cause is invisible. Add the trigger, or move the entry to never_required with the "
        "reason:\n  " + "\n  ".join(hangs)
    )


def test_every_required_check_is_a_job_that_exists():
    """A required check that names nothing reports nothing, and a check that
    never reports blocks every pull request forever. The name has to match a
    job's `name:` or its id exactly, which is worth asserting rather than
    proofreading."""
    missing = []
    for check, spec in sorted(REQUIRED.items()):
        available = _check_names(_workflow(spec["workflow"]))
        if check not in available:
            missing.append(f"{check!r} not among {sorted(available)} in {spec['workflow']}")
    assert not missing, (
        "These check names do not match any job in the workflow they are declared against, so branch protection would "
        "wait forever for a status nothing produces:\n  " + "\n  ".join(missing)
    )


def test_nothing_is_both_required_and_never_required():
    overlap = sorted(set(REQUIRED) & set(NEVER_REQUIRED))
    assert not overlap, "Declared in both required_status_checks and never_required:\n  " + "\n  ".join(overlap)


def test_the_never_required_reasons_are_still_true():
    """An exclusion justified by a missing `merge_group:` trigger stops being
    justified the day that trigger is added. This fails then - which is the
    moment the entry should move up rather than the moment somebody notices
    the gate was weaker than it could be."""
    now_eligible = []
    for check, spec in sorted(NEVER_REQUIRED.items()):
        parsed = _workflow(spec["workflow"])
        if "merge_group" in _triggers(parsed) and "pull_request" in _triggers(parsed):
            now_eligible.append(f"{check} (from {spec['workflow']})")
    assert not now_eligible, (
        "These are excluded from the required checks because their workflow could not report on a queue entry, and "
        "that is no longer true - the workflow now triggers on both `merge_group` and `pull_request`. Either move them "
        "into required_status_checks, or replace the `why` with the reason that still applies:\n  " + "\n  ".join(now_eligible)
    )


def test_require_branches_up_to_date_is_declared_off():
    """Not a preference. BRANCHING.md §1 is written around this being off, and
    turning it on makes the document's central instruction - do not merge
    `main` in to stay current - impossible to follow. Changing it here means
    changing that document too, which is what this assertion is for."""
    assert MANIFEST["settings"]["require_branches_up_to_date"]["expected"] is False, (
        "expected-protections.yml now expects `Require branches to be up to date before merging` to be ON. "
        "BRANCHING.md §1 says it must not be; if that has genuinely changed, that document changes in the same "
        "pull request as this line."
    )


# --- What only a live run can answer ---------------------------------------


@live
def test_the_required_checks_configured_are_the_ones_declared():
    configured = set(LIVE["required_status_checks"])
    declared = set(REQUIRED)

    assert configured == declared, (
        f"Branch protection on {BRANCH} requires a different set of checks than expected-protections.yml declares.\n"
        f"  configured but not declared: {sorted(configured - declared) or 'none'}\n"
        f"  declared but not configured: {sorted(declared - configured) or 'none'}\n"
        "RELEASING.md §8 gate 1 is what this is for; #375 is where the setting itself is tracked."
    )


@live
def test_no_never_required_check_is_configured():
    wrongly_required = sorted(set(LIVE["required_status_checks"]) & set(NEVER_REQUIRED))
    assert not wrongly_required, (
        "These are configured as required checks and must not be - each one hangs a merge queue entry or blocks every "
        "pull request. expected-protections.yml carries the measured reason for each:\n  " + "\n  ".join(wrongly_required)
    )


@live
def test_require_branches_up_to_date_is_actually_off():
    assert LIVE["require_branches_up_to_date"] is False, (
        "`Require branches to be up to date before merging` is ON for " + BRANCH + ". BRANCHING.md §1: this "
        "serialises concurrent work and makes the branching strategy unfollowable. Turn it off in Settings -> Rules."
    )


@live
def test_the_production_environment_asks_a_human():
    expected = MANIFEST["environments"]["production"]["required_reviewers_at_least"]
    actual = LIVE["environments"].get("production")

    assert actual is not None, (
        "There is no `production` environment, but publish-vector-data.yml and migrate.yml both run jobs under it. "
        "A job naming an environment that does not exist runs anyway, ungated."
    )
    assert actual >= expected, (
        f"The `production` environment has {actual} required reviewer(s), fewer than the {expected} expected. "
        "Nothing then asks a second time before a publish overwrites the map hikers download, or before a migration "
        "reaches the database a club moderates. RELEASING.md §12."
    )


@live
def test_the_release_labels_exist():
    missing = sorted(set(MANIFEST["labels"]) - set(LIVE["labels"]))
    assert not missing, (
        "These labels do not exist, so RELEASING.md gate 11 cannot be answered: a search for a label nothing carries "
        "returns no issues, which reads exactly like a clean gate:\n  " + "\n  ".join(missing)
    )


def test_the_live_check_is_not_silently_skipping_where_it_is_meant_to_run():
    """Everything above marked @live skips when its environment is absent,
    which is correct locally and would be a silent pass in the one job whose
    entire purpose is to run them. Borrowed wholesale from
    test_repository_settings.py, which learned it first."""
    if os.environ.get("PROTECTIONS_CHECK_LIVE") != "1":
        pytest.skip("Not the job that checks the live protections.")
    assert LIVE is not None, (
        "This job is meant to check how GitHub is configured, but LIVE_PROTECTIONS did not arrive, so every live test "
        "skipped and the job would have passed having checked nothing. The most likely cause is the API refusing a "
        "read: branch protection and environments need `administration: read`, which protections-check.yml requests "
        "and an organization policy can still withhold."
    )
