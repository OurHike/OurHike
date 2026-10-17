"""promote-data.yml cannot move production's pointer unattended.

The maintainer, 2026-10-16: promoting a data release to production copies the
release UA was tested on and moves production's channels.json, and it runs
only by a person's dispatch behind the production environment's reviewer.
pipeline/channels.py does the copy and the move (pipeline/tests/test_channels.py
holds what it refuses); this holds the workflow around it: how it can start,
which environment's reviewer it waits on, and that a confirmation not naming
its own target stops it before any secret is read.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
NAME = "promote-data.yml"
PUBLIC_BUCKET_SECRETS = {"R2_ENDPOINT_URL", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load((WORKFLOWS / NAME).read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as True.
    return workflow.get("on", workflow.get(True))


def test_it_starts_only_by_a_dispatch(workflow):
    assert set(_triggers(workflow)) == {"workflow_dispatch"}


def test_no_other_workflow_starts_it():
    """A `gh workflow run promote-data.yml` in a scheduled workflow would make it unattended in all but name."""
    for path in WORKFLOWS.glob("*.yml"):
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (parsed.get("jobs") or {}).values():
            assert NAME not in str(job.get("uses") or ""), path.name
            for step in job.get("steps") or []:
                assert NAME not in str(step.get("run") or ""), f"{path.name}: {step.get('name')}"


def test_its_inputs_are_the_target_release_schema_version_and_a_required_confirmation(workflow):
    inputs = _triggers(workflow)["workflow_dispatch"]["inputs"]

    assert set(inputs) == {"target", "release", "schema_version", "confirm"}
    assert inputs["target"]["type"] == "choice" and inputs["target"]["options"] == ["production", "ua"]
    assert inputs["target"]["default"] == "production"
    assert inputs["release"]["default"] == "", "empty: UA's current release"
    assert inputs["schema_version"]["default"] == "v1"
    assert inputs["confirm"]["required"] is True and "default" not in inputs["confirm"]


def test_a_production_promotion_waits_on_the_production_environments_reviewer(workflow):
    """`target` is a choice of production or ua, so the expression yields the literal `production` for a promotion,
    the environment .github/expected-protections.yml requires a reviewer on."""
    (job,) = workflow["jobs"].values()

    assert job["environment"] == "${{ inputs.target == 'production' && 'production' || 'ua' }}"
    protections = yaml.safe_load((WORKFLOWS.parent / "expected-protections.yml").read_text(encoding="utf-8"))
    assert protections["environments"]["production"]["required_reviewers_at_least"] >= 1
    assert "promote-data.yml" in protections["environments"]["production"]["why"]


def test_it_shares_publish_data_and_reads_only_its_own_inputs_through_env(workflow):
    (job,) = workflow["jobs"].values()

    assert job["concurrency"] == {"group": "publish-data", "cancel-in-progress": False}
    assert workflow["permissions"] == {"contents": "read"}
    for step in job["steps"]:
        assert "inputs." not in str(step.get("run") or ""), step.get("name")


def test_the_confirmation_is_checked_first_and_holds_no_secret(workflow):
    (job,) = workflow["jobs"].values()
    first = job["steps"][0]

    assert "uses" not in first
    assert not set(first.get("env") or {}) & PUBLIC_BUCKET_SECRETS


@pytest.mark.parametrize(
    ("target", "confirm", "passes"),
    [
        ("production", "promote to production", True),
        ("ua", "promote to ua", True),
        ("production", "promote to ua", False),
        ("production", "yes", False),
        ("production", "", False),
        ("production", "promote to production ", False),
    ],
)
def test_a_confirmation_not_naming_its_target_stops_the_run(workflow, target, confirm, passes):
    (job,) = workflow["jobs"].values()
    script = job["steps"][0]["run"]

    completed = subprocess.run(
        ["bash", "-e", "-c", script],
        env={**os.environ, "TARGET": target, "CONFIRM": confirm},
        capture_output=True,
        text=True,
    )

    assert (completed.returncode == 0) is passes, completed.stdout + completed.stderr


def test_the_move_is_channels_py_promote_from_ua_with_writes_enabled_on_that_step_alone(workflow):
    (job,) = workflow["jobs"].values()
    writers = [step for step in job["steps"] if "R2_WRITE_ENABLED" in (step.get("env") or {})]

    assert len(writers) == 1
    (step,) = writers
    assert step["run"].startswith('python channels.py promote --from ua --to "$TARGET"')
    assert PUBLIC_BUCKET_SECRETS <= set(step["env"])
    assert step["env"]["TARGET"] == "${{ inputs.target }}"
