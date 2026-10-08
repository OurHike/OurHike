"""purge-person-fields.yml, decision 56's purge: dispatch-only with the placeholder's one input, the raw store's key and
nothing else, one run at a time with the monthly lane, and --delete passed only when a person asked for it.

PR #1827 - Add dispatch-only build-reference.yml and purge-person-fields.yml placeholders to main - put a placeholder
of this file on `main`, because GitHub takes a dispatch only for a workflow whose file is on the default branch. The
same `gh workflow run ... -f delete=false` must be valid against both, so the `on:` block here is held to the
placeholder's, word for word. What the purge itself does is pipeline/purge_person_fields.py's, and
pipeline/tests/test_purge_person_fields.py holds it.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from test_refresh_reference import BASH, PUBLIC_BUCKET_SECRETS, RAW_STORE_SECRETS, WORKFLOWS, _load, _secrets, _triggers

NAME = "purge-person-fields.yml"
#: The placeholder's `on:` block, as PR #1827 put it on main (its .github/workflows/purge-person-fields.yml, read
#: 2026-10-08 from the pull request's diff).
PLACEHOLDER_TRIGGERS = {
    "workflow_dispatch": {
        "inputs": {
            "delete": {
                "description": "false lists every stored object holding a person field; true deletes them",
                "type": "boolean",
                "default": False,
            }
        }
    }
}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return _load(WORKFLOWS / NAME)


def _purge_step(workflow: dict) -> dict:
    (step,) = [step for step in workflow["jobs"]["purge"]["steps"] if "purge_person_fields.py" in (step.get("run") or "")]
    return step


def test_its_one_trigger_is_a_dispatch_with_exactly_the_placeholders_one_input(workflow):
    assert _triggers(workflow) == PLACEHOLDER_TRIGGERS


def test_it_holds_the_raw_stores_key_and_no_other(workflow):
    """Only the raw store's four names, and never the public bucket's: nothing here writes what a phone reads."""
    (job,) = workflow["jobs"].values()

    assert _secrets(job) == RAW_STORE_SECRETS | {"R2_ENDPOINT_URL"}
    assert not _secrets(job) & PUBLIC_BUCKET_SECRETS
    assert "environment" not in job


def test_its_permissions_are_reading_the_checkout_and_nothing_more(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    assert all("permissions" not in job for job in workflow["jobs"].values())


def test_it_never_runs_beside_the_monthly_lane(workflow):
    """refresh-reference.yml and build-reference.yml write the monthly prefix and the step cache under this group."""
    refresh = _load(WORKFLOWS / "refresh-reference.yml")
    build = _load(WORKFLOWS / "build-reference.yml")

    assert workflow["concurrency"] == refresh["concurrency"] == build["concurrency"]
    assert workflow["concurrency"] == {"group": "raw-lake-monthly", "cancel-in-progress": False}


def test_it_has_a_timeout_and_dlts_telemetry_is_off(workflow):
    (job,) = workflow["jobs"].values()

    assert isinstance(job.get("timeout-minutes"), int)
    assert workflow["env"]["RUNTIME__DLTHUB_TELEMETRY"] == "false"


def test_the_store_is_reached_under_the_same_names_the_monthly_lanes_pin_job_uses(workflow):
    """dlt's filesystem client reads DESTINATION__FILESYSTEM__CREDENTIALS__*: the same names, from the same secrets,
    as refresh-reference.yml's "Pin this run's raw inputs" step, so one key set reaches both."""
    refresh = _load(WORKFLOWS / "refresh-reference.yml")
    (pin,) = [step for step in refresh["jobs"]["pin"]["steps"] if step.get("name") == "Pin this run's raw inputs"]

    env = _purge_step(workflow)["env"]
    credentials = {name: value for name, value in env.items() if name.startswith("DESTINATION__") or name == "R2_RAW_BUCKET"}
    assert credentials == pin["env"]


def _run_the_purge_step(workflow: dict, tmp_path: Path, delete: str) -> list[str]:
    """The purge step's script as GitHub runs it, with a stand-in python in the extract's venv that logs its argv."""
    venv = tmp_path / "extract" / "bin"
    venv.mkdir(parents=True)
    log = tmp_path / "argv.json"
    stub = venv / "python"
    stub.write_text(
        "#!/usr/bin/env python3\nimport json, os, sys\nopen(os.environ['ARGV_LOG'], 'w').write(json.dumps(sys.argv[1:]))\n"
    )
    stub.chmod(0o755)
    completed = subprocess.run(
        [*BASH, _purge_step(workflow)["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "ARGV_LOG": str(log),
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            "R2_RAW_BUCKET": "our-hike-raw",
            "DELETE": delete,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(log.read_text())


def test_delete_false_lists_only(workflow, tmp_path):
    argv = _run_the_purge_step(workflow, tmp_path, "false")

    assert argv[0] == "purge_person_fields.py" and "--delete" not in argv
    assert argv[argv.index("--raw-bucket") + 1] == "our-hike-raw"
    assert argv[argv.index("--summary") + 1] == str(tmp_path / "summary.md")


def test_delete_true_is_the_only_thing_that_passes_delete(workflow, tmp_path):
    """A boolean input reaches the script as the text `true` or `false`, through env, never pasted into it."""
    assert "--delete" in _run_the_purge_step(workflow, tmp_path, "true")
    assert _purge_step(workflow)["env"]["DELETE"] == "${{ inputs.delete }}"
    assert "inputs." not in _purge_step(workflow)["run"]
