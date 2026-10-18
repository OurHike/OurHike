"""The data-environment switch reaches every build that publishes, and no build that tests.

The maintainer, 2026-10-15: "Every test should have both the warning and error thresholds. If an error like
freshness would prevent building the model, then that should be enabled/disabled based on the environment. prod
environment should ignore those, dev & ci should not." OURHIKE_DATA_ENV is the one
switch: pipeline/dbt/dbt_project.yml reads it for every test's severity, and
pipeline/build_marts.py for whether a failure stops the build or holds what it reaches (its docstring, "EVERY TEST
HAS TWO THRESHOLDS, AND THE ENVIRONMENT DECIDES WHO STOPS").

So each lane's step that runs build_marts.py names its environment, the one it publishes to, and CI's fixture build
names none, which dbt and build_marts.py both read as dev: a step that dropped it would build production's files as
dev builds them, stopping the hour on what production builds past, and a CI step that gained one would build past
the errors CI exists to stop on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
NAME = "OURHIKE_DATA_ENV"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _build_marts_steps(workflow: dict) -> list[tuple[str, dict, dict]]:
    """(job id, job, step) for every step whose script runs build_marts.py, rather than names it in a message."""
    return [
        (job_id, job, step)
        for job_id, job in workflow["jobs"].items()
        for step in job.get("steps") or []
        if "python build_marts.py" in str(step.get("run") or "")
    ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("build-reference.yml", "ua"),
        ("publish-conditions.yml", "${{ matrix.data_environment }}"),
        ("check-conditions.yml", "${{ matrix.data_environment }}"),
    ],
)
def test_every_lane_step_that_runs_build_marts_names_the_environment_it_publishes_to(name, expected):
    steps = _build_marts_steps(_load(name))
    assert steps, f"{name} runs build_marts.py"
    for _, _, step in steps:
        assert (step.get("env") or {}).get(NAME) == expected, f"{name}: {step.get('name')}"


def test_ci_builds_the_fixtures_as_dev_so_every_error_stops_it():
    workflow = _load("pipeline-tests.yml")
    steps = _build_marts_steps(workflow)
    assert steps, "pipeline-tests.yml's dbt job runs build_marts.py --fixtures"
    assert NAME not in (workflow.get("env") or {})
    for job_id, job, step in steps:
        assert NAME not in (job.get("env") or {}), job_id
        assert NAME not in (step.get("env") or {}), step.get("name")
        assert NAME not in str(step.get("run")), step.get("name")
