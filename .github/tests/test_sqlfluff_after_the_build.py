"""SQLFluff runs on every core, after the dbt job's build and its tests, and still inside the required `dbt` job.

SQLFluff was the dbt job's first step, on one process, from when it linted 32
files in 3.8 s. The project now lints 1,446 SQL files, and the step took
19 m 31 s on run 37246416152 and 25 m 35 s on run 37248247711, so a build that
failed was reported 20 minutes later than it had to be (WF7 of the PR #1805
review). It moves to the end of the job, runs whatever the build did unless
the run was cancelled, so one round trip still reports both, and runs with
`--processes 0`, SQLFluff's "every CPU".

It stays a step of the `dbt` job, never a job of its own: `dbt` is a required
check (.github/expected-protections.yml), and a new job would be a check the
branch ruleset does not require until somebody changes the ruleset by hand.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pipeline-tests.yml"
TEST_SH = ROOT / "scripts" / "test.sh"


def _steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["dbt"]["steps"]


def _index(steps: list[dict], needle: str) -> int:
    (index,) = [index for index, step in enumerate(steps) if needle in str(step.get("run", ""))]
    return index


def test_sqlfluff_runs_on_every_core_after_the_build_and_the_evaluator_in_the_required_dbt_job():
    steps = _steps()
    lint = _index(steps, "sqlfluff lint")

    assert "--processes 0" in steps[lint]["run"]
    assert lint > _index(steps, "build_marts.py --fixtures"), "the build reports before the lint"
    assert lint > _index(steps, "package:dbt_project_evaluator"), "and so does every test after it"


def test_sqlfluff_still_runs_when_the_build_failed_but_not_when_the_packages_are_missing():
    """dbt_utils' macros render from dbt_packages/, so the lint needs the packages, from the cache or from deps."""
    steps = _steps()
    condition = " ".join(str(steps[_index(steps, "sqlfluff lint")]["if"]).split())

    assert condition.startswith("!cancelled() && steps.scope.outputs.run == 'true'")
    assert "(steps.dbt-packages.outputs.cache-hit == 'true' || steps.deps.outcome == 'success')" in condition


def test_test_sh_lints_on_every_core_after_its_dbt_build_as_ci_does():
    text = TEST_SH.read_text(encoding="utf-8")
    (lint,) = [line for line in text.splitlines() if 'step "dbt sqlfluff lint"' in line]

    assert "--processes 0" in lint
    assert text.index('step "dbt sqlfluff lint"') > text.index('step "dbt project evaluator"')
