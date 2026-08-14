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
through the environment. Nothing it hands over is a credential - branch
protection, environments and labels are configuration - so unlike the settings
check this file can print what it found.

It can also arrive incomplete, which is the one thing worth understanding
before reading a green run. **GITHUB_TOKEN has no scope for repository
administration at all**: `administration: read` is not a key a workflow
`permissions:` block accepts, and asking for it does not warn - it makes the
file invalid, so every run is a startup failure with zero jobs. Three of those
landed on `main` before anyone noticed. The environments and *classic* branch
protection are therefore readable only with a fine-grained PAT, which is
optional, so those sections may be absent while the labels are always present.
`_needs` is how a test says which section it depends on.

**A branch's RULESETS need no PAT** (#685), which is the one asymmetry worth
knowing here. Rulesets and classic branch protection are separate GitHub
features with separate endpoints, and neither reports the other's rules -
this file's live half spent its whole life reading only the classic one while
a ruleset was what actually protected `main`, reporting five required checks
as absent. The rules that apply to a branch are readable with GITHUB_TOKEN, so
what a run cannot see without the PAT is now the environments and a classic
protection that, here, does not exist.

**Why the asymmetry with #375 matters.** Making these settings is a human
action - no API this repository can reach will do it, which is why #375 is
open at all. What is automatable is noticing, and noticing is the difference
between a gate that was true the day it was configured and one that is true
now.
"""

from __future__ import annotations

import json
import os
from itertools import product
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

    A plain job reports its `name:` where it has one and its job id
    otherwise. This is the string the branch protection setting has to
    match, and getting it wrong produces a required check that never
    reports - which blocks every pull request rather than failing one.

    A MATRIX job never reports its bare name (#654): GitHub reports one
    check per leg, `id (value, value, ...)`, so a default-named plain-list
    matrix is expanded here and its bare id is deliberately absent. Anything
    this checkout cannot expand with certainty - include/exclude, non-scalar
    axes, an explicit or templated `name:` on a matrix job, or a
    reusable-workflow job (which reports `caller / callee`) - contributes
    NOTHING, so requiring it fails the exists-test at the pull request that
    adds it. That is the only cheap moment: the same mistake caught live is
    every pull request blocked behind a status nothing will ever report.
    """
    names = set()
    for job_id, job in (parsed.get("jobs") or {}).items():
        if not isinstance(job, dict):
            names.add(job_id)
            continue
        if "uses" in job:
            continue
        strategy = job.get("strategy")
        matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
        if matrix is None:
            names.add(job.get("name") or job_id)
            continue
        if job.get("name") or not isinstance(matrix, dict) or "include" in matrix or "exclude" in matrix:
            continue
        axes = list(matrix.values())
        if not all(
            isinstance(values, list) and all(isinstance(value, (str, int, float, bool)) for value in values) for values in axes
        ):
            continue
        for combo in product(*axes):
            names.add(f"{job_id} ({', '.join(str(value) for value in combo)})")
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


def _needs(section: str):
    """Skip when this run could not ask the question at all.

    Not the same as skipping a refused read, which fails the job instead.
    GITHUB_TOKEN has no scope for repository administration - there is no
    permissions block that grants it - so the environments are readable only
    with a fine-grained PAT in PROTECTIONS_READ_TOKEN, and that secret is
    optional. Absent, this reports which sections it could not see rather than
    turning `main` red for a state that is declared; present but refused, the
    workflow fails before pytest runs at all.

    Since #685 `branch_protection` is no longer in that PAT-only set. It is
    reported when EITHER source answered - the ruleset read, which needs no
    PAT, or classic protection, which does - because the question the manifest
    asks is "what protects this branch", not "which endpoint answered".
    """
    return pytest.mark.skipif(
        LIVE is not None and section not in LIVE.get("read", []),
        reason=f"{section} was not read. See protections-check.yml.",
    )


def _answered(value, what: str):
    """Fail rather than assert against a value nobody read.

    #685's real damage was not the false alarm, it was this: with the ruleset
    invisible, `strict` and the approval count fell back to defaults that
    happened to be the values the manifest wants, so both tests guarding the
    solo-maintainer lockouts passed having read nothing. protections-check.yml
    now leaves them null when unread, and this turns that null into a failure
    instead of a comparison that accidentally succeeds.
    """
    assert value is not None, (
        f"{what} came back null, which means protections-check.yml could not read it from either classic branch "
        "protection or the branch's rulesets. A test that compares a null against what the manifest expects is the "
        "#685 failure - passing by reading nothing - so this fails instead. Check the run's `sections read` line."
    )
    return value


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
        "These check names do not match any check the workflow will report, so branch protection would wait forever "
        "for a status nothing produces. (A matrix job's bare name is deliberately not on the menu - it reports one "
        "check per LEG - and a job _check_names cannot expand with certainty offers nothing at all; see #654.)\n  "
        + "\n  ".join(missing)
    )


def test_a_matrix_job_reports_one_check_per_leg_never_its_bare_name():
    """The blindness #654 names: give client-tests' `test` job a node matrix
    and the bare name `test` stops reporting forever, while the manifest, the
    old checkout test, and the weekly live comparison all stayed green - and
    every pull request blocked. The legs are the menu; the bare name is not."""
    parsed = {"jobs": {"test": {"strategy": {"matrix": {"node": [22, 24]}}, "steps": []}}}

    assert _check_names(parsed) == {"test (22)", "test (24)"}


def test_a_two_axis_matrix_expands_every_combination():
    parsed = {"jobs": {"t": {"strategy": {"matrix": {"a": [1, 2], "b": ["x"]}}, "steps": []}}}

    assert _check_names(parsed) == {"t (1, x)", "t (2, x)"}


def test_a_matrix_this_file_cannot_expand_offers_nothing_rather_than_a_guess():
    """include/exclude and explicit or templated names change what GitHub
    reports in ways a checkout cannot re-derive. Refusing to guess means
    requiring such a job fails test_every_required_check_is_a_job_that_exists
    loudly - instead of blessing a name that blocks production (#654)."""
    include = {"jobs": {"test": {"strategy": {"matrix": {"include": [{"node": 22}]}}, "steps": []}}}
    named = {"jobs": {"test": {"name": "suite", "strategy": {"matrix": {"node": [22]}}, "steps": []}}}
    reusable = {"jobs": {"test": {"uses": "./.github/workflows/other.yml"}}}

    assert _check_names(include) == set()
    assert _check_names(named) == set()
    assert _check_names(reusable) == set()


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


def test_the_solo_maintainer_lockouts_are_declared_at_their_safe_values():
    """Both settings that can make this repository unusable by the only person
    who can use it, asserted from the checkout so a change to the manifest is
    caught on the pull request that proposes it rather than by the weekly run.

    They point opposite ways, which is the whole reason for stating them
    together: a pull request approval requirement locks a solo maintainer out
    when it is ON, and an environment's self-review prevention locks them out
    when it is ON, while the environment's *reviewer* requirement is the one
    thing here that should be on.
    """
    assert MANIFEST["settings"]["required_approving_review_count"]["expected"] == 0, (
        "expected-protections.yml now expects pull request approvals to be required. Nobody can approve their own "
        "pull request on GitHub, so with one maintainer that is a repository nothing can be merged into. If a second "
        "person has joined, say so here and in RELEASING.md §9 in the same pull request."
    )
    assert MANIFEST["environments"]["production"]["prevent_self_review"] is False, (
        "expected-protections.yml now expects `Prevent self-review` on the production environment. With a single "
        "required reviewer that is a lockout: the only reviewer is always the dispatcher, so nothing can be approved."
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


def test_the_checker_reads_both_systems_that_can_protect_a_branch():
    """The from-a-checkout half of #685, and the reason it is a test rather
    than a comment.

    Classic branch protection and rulesets are separate GitHub features with
    separate endpoints, and neither reports the other's rules. Reading only
    `getBranchProtection` is what let this workflow report `main` as bare for
    its entire life while a ruleset required five checks on it - and nothing
    failed, because the values it fell back to happened to be the ones the
    manifest wanted.

    A live run cannot catch a regression here: dropping the ruleset read would
    put the workflow straight back to green-and-wrong. So the assertion is
    about the file, where it can fail on the pull request that proposes it.
    """
    source = (WORKFLOW_DIR / "protections-check.yml").read_text(encoding="utf-8")
    missing = [call for call in ("rules/branches/{branch}", "getBranchProtection") if call not in source]
    assert not missing, (
        "protections-check.yml no longer reads every system that can protect a branch, so a branch protected by "
        "the system it stopped reading would report as unprotected - which is #685, the bug this test exists for. "
        "Missing: " + ", ".join(missing)
    )


# --- What only a live run can answer ---------------------------------------


@live
@_needs("branch_protection")
def test_the_required_checks_configured_are_the_ones_declared():
    configured = set(_answered(LIVE["required_status_checks"], "The set of required status checks"))
    declared = set(REQUIRED)

    assert configured == declared, (
        f"Branch protection on {BRANCH} requires a different set of checks than expected-protections.yml declares.\n"
        f"  configured but not declared: {sorted(configured - declared) or 'none'}\n"
        f"  declared but not configured: {sorted(declared - configured) or 'none'}\n"
        "RELEASING.md §8 gate 1 is what this is for; #375 is where the setting itself is tracked."
    )


@live
@_needs("branch_protection")
def test_no_never_required_check_is_configured():
    configured = _answered(LIVE["required_status_checks"], "The set of required status checks")
    wrongly_required = sorted(set(configured) & set(NEVER_REQUIRED))
    assert not wrongly_required, (
        "These are configured as required checks and must not be - each one hangs a merge queue entry or blocks every "
        "pull request. expected-protections.yml carries the measured reason for each:\n  " + "\n  ".join(wrongly_required)
    )


@live
@_needs("branch_protection")
def test_require_branches_up_to_date_is_actually_off():
    assert _answered(LIVE["require_branches_up_to_date"], "`Require branches to be up to date`") is False, (
        "`Require branches to be up to date before merging` is ON for " + BRANCH + ". BRANCHING.md §1: this "
        "serialises concurrent work and makes the branching strategy unfollowable. Turn it off in Settings -> Rules."
    )


@live
@_needs("branch_protection")
def test_no_pull_request_approval_is_required():
    """The lockout, not a preference.

    GitHub does not let an author approve their own pull request - a platform
    rule with no toggle, unlike everything else this file checks. With one
    maintainer, requiring an approval means no pull request is ever mergeable,
    including the agent-authored ones: the token authenticates as the
    maintainer, so GitHub considers those theirs too.
    """
    expected = MANIFEST["settings"]["required_approving_review_count"]["expected"]
    actual = _answered(LIVE["required_approving_review_count"], "The required approving review count")

    assert actual == expected, (
        f"{BRANCH} requires {actual} approving review(s). This repository has one maintainer, and GitHub does not "
        "let anyone approve their own pull request - so nothing can ever be merged without an admin bypass, which "
        "hollows out the rule it was meant to enforce. Set it to 0, or revisit this line when there is a second "
        "person to give the approval."
    )


@live
@_needs("environments")
def test_the_production_environment_asks_a_human():
    expected = MANIFEST["environments"]["production"]["required_reviewers_at_least"]
    actual = LIVE["environments"].get("production")

    assert actual is not None, (
        "There is no `production` environment, but publish-vector-data.yml and migrate.yml both run jobs under it. "
        "A job naming an environment that does not exist runs anyway, ungated."
    )
    assert actual["reviewers"] >= expected, (
        f"The `production` environment has {actual['reviewers']} required reviewer(s), fewer than the {expected} "
        "expected. Nothing then asks a second time before a publish overwrites the map hikers download, or before a "
        "migration reaches the database a club moderates. RELEASING.md §12."
    )


@live
@_needs("environments")
def test_the_production_environment_does_not_prevent_self_review():
    """The other lockout, and the one that inverts the pull-request rule.

    GitHub lets a required reviewer approve their own deployment by default;
    "Prevent self-review" is an opt-in toggle. Off, one maintainer can be
    their own reviewer and the gate still does real work - a publish waits for
    a deliberate approval rather than firing on dispatch. On, with a single
    reviewer, nobody can ever approve and both workflows under this
    environment become undispatchable.
    """
    production = LIVE["environments"].get("production")
    if production is None:
        pytest.skip("No production environment yet - test_the_production_environment_asks_a_human is the failure.")

    expected = MANIFEST["environments"]["production"]["prevent_self_review"]

    assert production["prevent_self_review"] == expected, (
        "The `production` environment has `Prevent self-review` ON. With one maintainer that is a lockout rather "
        "than a tightening: the only required reviewer is always the person who dispatched, so no publish and no "
        "production migration can ever be approved. Turn it off until there is a second reviewer."
    )


@live
@_needs("labels")
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
    assert LIVE is not None and LIVE.get("read"), (
        "This job read nothing at all. Even without PROTECTIONS_READ_TOKEN the labels are readable with "
        "GITHUB_TOKEN, so an empty `read` means the reading step did not run or produced no output - and every live "
        "test below skipped, leaving a green job that checked nothing. (Not a permissions diagnosis: the workflow "
        "token CANNOT request `administration: read` - protections-check.yml's header explains the invalid-key "
        "startup failures that proved it - which is why the CLASSIC protection and environment reads ride "
        "PROTECTIONS_READ_TOKEN and their absence alone is the three-outcome design working. A second assert here "
        "used to claim the opposite, from a branch no input could reach - #654.)"
    )
    # `read` is seeded with 'labels' before anything else is attempted, so the
    # assertion above cannot fail once the step runs at all - which is how the
    # guard-the-guard came to have the same blind spot as the thing it guards.
    # #685: branch protection was unreadable for the entire life of this
    # workflow and every run above was green about it.
    #
    # The branch rules need no PAT, so in the live job there is no legitimate
    # reason for them to be missing. Naming that section specifically is what
    # makes this assertion able to fail.
    assert "branch_rules" in LIVE.get("read", []), (
        "The branch's rulesets were not read, and unlike the classic-protection and environment reads this one "
        "needs no PAT - `GET /repos/{owner}/{repo}/rules/branches/{branch}` answers to GITHUB_TOKEN. So this is a "
        "broken read rather than an absent credential, and it is the one that matters: rulesets are what actually "
        "protect `main`, and #685 is the whole life of this workflow reporting them as absent. "
        f"Sections read: {LIVE.get('read')}."
    )
