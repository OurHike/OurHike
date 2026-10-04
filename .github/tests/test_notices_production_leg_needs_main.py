"""extract-notices.yml runs its production leg only from main, whatever a dispatch asks for.

The notices job (decision 61) fills each environment's notices store, and
production's is the one publish-conditions.yml's production leg will build
hikers' closures and warnings from once the dbt path is cut over. A schedule
fires from main alone, but `workflow_dispatch` runs any ref, with that ref's
copy of the workflow, and decision 62's soak dispatches this workflow from
the pull request's branch. So it carries publish-conditions.yml's two locks,
and this file holds both the same way
test_conditions_production_leg_needs_main.py does, with that file's
evaluator of GitHub's expression language:

1. The matrix leaves the production leg out unless `github.ref` is
   `refs/heads/main` and the dispatch did not ask for `ua` alone, evaluated
   for every trigger, ref and input below.
2. The job's first step refuses a production leg from any other ref, with
   bash's case-sensitive `=`, because GitHub's `==` ignores case and a
   branch named `Main` passes lock 1. The step's own script runs here.

It has no `phone_files` input and so no third lock: it publishes nothing.
"""

from __future__ import annotations

import json
import re
import subprocess
from itertools import product
from pathlib import Path

import pytest
import yaml

from test_conditions_production_leg_needs_main import INPUTS, MAIN, OTHER_REFS, _evaluate, _expression

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "extract-notices.yml"
JOB = "extract"
GUARD_STEP = "Refuse a production leg from any ref but main"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True.
    return workflow.get("on", workflow.get(True)) or {}


def _legs(ref: str, data_environment: str | None, event: str) -> list[str]:
    matrix = _workflow()["jobs"][JOB]["strategy"]["matrix"]
    assert set(matrix) == {"data_environment"}, f"the matrix has {sorted(matrix)}; an include would add legs unevaluated"
    inputs = {} if data_environment is None else {"data_environment": data_environment}
    return _evaluate(_expression(matrix["data_environment"]), {"github": {"ref": ref, "event_name": event}, "inputs": inputs})


def _guard(leg: str, ref: str, asked: str | None) -> subprocess.CompletedProcess:
    step = _workflow()["jobs"][JOB]["steps"][0]
    env = {"LEG": leg, "REF": ref, "ASKED": asked or "", "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", "-e", "-c", step["run"]], env=env, capture_output=True, text=True)


def test_only_a_schedule_and_a_dispatch_start_this_workflow():
    assert set(_triggers(_workflow())) == {"schedule", "workflow_dispatch"}


@pytest.mark.parametrize(("ref", "asked"), list(product(OTHER_REFS, INPUTS)))
def test_a_run_from_any_ref_but_main_never_reaches_the_production_leg(ref, asked):
    legs = _legs(ref, asked, "workflow_dispatch")
    assert "ua" in legs, f"{ref} with data_environment={asked!r} gave {legs}: the UA leg must still run"
    if "production" in legs:
        refused = _guard("production", ref, asked)
        assert refused.returncode != 0, f"{ref} with {asked!r} let the production leg past: {refused.stdout}{refused.stderr}"
        assert "Production leg refused" in refused.stdout


def test_a_branch_that_github_reads_as_main_is_stopped_by_the_first_step():
    assert "production" in _legs("refs/heads/Main", "both", "workflow_dispatch")
    assert _guard("production", "refs/heads/Main", "both").returncode != 0


def test_the_schedule_and_a_main_dispatch_run_both_legs():
    assert _legs(MAIN, None, "schedule") == ["production", "ua"]
    assert _legs(MAIN, "both", "workflow_dispatch") == ["production", "ua"]
    assert _legs(MAIN, "ua", "workflow_dispatch") == ["ua"]
    assert _guard("production", MAIN, None).returncode == 0
    assert _guard("ua", MAIN, None).returncode == 0


def test_every_data_environment_choice_is_one_this_file_evaluates():
    choice = _triggers(_workflow())["workflow_dispatch"]["inputs"]["data_environment"]
    assert choice["type"] == "choice" and set(choice["options"]) == {value for value in INPUTS if value}
    assert set(_triggers(_workflow())["workflow_dispatch"]["inputs"]) == {"data_environment"}


def test_the_refusal_is_the_first_step_and_nothing_after_it_runs_regardless():
    """A refused production leg reads no secret and writes nothing: the refusal runs first on every leg, and no
    step that holds the raw store's key asks to run after a failure."""
    steps = _workflow()["jobs"][JOB]["steps"]
    assert steps[0].get("name") == GUARD_STEP
    assert "if" not in steps[0], "the refusal must run on every leg, not only when a condition holds"
    assert "secrets." not in json.dumps(steps[0])
    sensitive = [step for step in steps[1:] if "secrets." in json.dumps(step.get("env") or {})]
    assert sensitive, "no step holds a secret, so this test checks nothing"
    runs_regardless = [
        step.get("name") for step in sensitive if re.search(r"\b(always|failure|cancelled)\(", str(step.get("if", "")))
    ]
    assert runs_regardless == [], f"these would run after a refused first step: {runs_regardless}"
