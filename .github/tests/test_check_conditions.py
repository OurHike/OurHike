"""check-conditions.yml, the hourly lane's checks (decision 110), and the job of publish-conditions.yml that starts them.

The maintainer's poll of 2026-10-08: "All of them, hourly. build a different workflow that kicks off after the actual
build". What is held here is what keeps that workflow out of a hiker's way and inside the hour:

- its inputs are the placeholder's on main (PR #1827 - Add dispatch-only build-reference.yml, purge-person-fields.yml
  and check-conditions.yml placeholders to main), since a dispatch is taken only for a file main holds;
- publish-conditions.yml starts it once both legs have published, on the legs that ran, with `actions: write` on that
  job alone and every word of the command through env;
- each leg shares its concurrency group with publish-conditions.yml's leg, and neither holds publish-data for it;
- it writes one object, conditions/data_quality.json, through `publish.py --sidecar`, after the checks succeeded;
- the warehouse crosses through the leg's history store, never an Actions artifact;
- the caps of a build and its checks add to less than the hour between two runs.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from itertools import product
from pathlib import Path

import pytest
import yaml

from test_conditions_production_leg_needs_main import MAIN, OTHER_REFS, PHONE_FILES, _evaluate, _expression

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
CHECKS = WORKFLOWS / "check-conditions.yml"
BAKE = WORKFLOWS / "publish-conditions.yml"
BUILD_RUN = "37800000001"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True)) or {}


def _steps(path: Path, job: str) -> list[dict]:
    return _load(path)["jobs"][job]["steps"]


def _step(path: Path, job: str, name: str) -> dict:
    (step,) = [step for step in _steps(path, job) if step.get("name") == name]
    return step


# --- the inputs, the placeholder's -------------------------------------------------------------------------------

#: The workflow_dispatch block of PR #1827's placeholder, read with mcp's pull_request_read on 2026-10-08.
PLACEHOLDER_INPUTS = {
    "data_environment": {
        "description": "Which legs' builds to check: both (production and UA; from main only) or ua alone",
        "type": "choice",
        "options": ["both", "ua"],
        "default": "both",
    },
    "build_run": {
        "description": "The publish-conditions.yml run whose build these checks read",
        "type": "string",
        "required": True,
    },
}


def test_it_is_dispatch_only_with_exactly_the_placeholders_inputs():
    triggers = _triggers(_load(CHECKS))
    assert set(triggers) == {"workflow_dispatch"}, "never a schedule: publish-conditions.yml starts it after each build"
    assert triggers["workflow_dispatch"]["inputs"] == PLACEHOLDER_INPUTS


# --- which legs ---------------------------------------------------------------------------------------------------


def _bake_legs(ref: str, data_environment: str | None, phone_files: str | None, event: str) -> list[str]:
    matrix = _load(BAKE)["jobs"]["publish"]["strategy"]["matrix"]["data_environment"]
    inputs = {key: value for key, value in (("data_environment", data_environment), ("phone_files", phone_files)) if value}
    return _evaluate(_expression(matrix), {"github": {"ref": ref, "event_name": event}, "inputs": inputs})


def _dispatched_legs(ref: str, data_environment: str | None, phone_files: str | None, event: str) -> str:
    env = _step(BAKE, "checks", "Dispatch check-conditions.yml on this ref, with this run as its build_run")["env"]
    inputs = {key: value for key, value in (("data_environment", data_environment), ("phone_files", phone_files)) if value}
    return _evaluate(_expression(env["LEGS"]), {"github": {"ref": ref, "event_name": event}, "inputs": inputs})


def _checks_legs(ref: str, data_environment: str) -> list[str]:
    matrix = _load(CHECKS)["jobs"]["check"]["strategy"]["matrix"]
    assert set(matrix) == {"data_environment"}, "an include or exclude would add legs this test does not evaluate"
    context = {"github": {"ref": ref, "event_name": "workflow_dispatch"}, "inputs": {"data_environment": data_environment}}
    return _evaluate(_expression(matrix["data_environment"]), context)


@pytest.mark.parametrize(
    ("ref", "data_environment", "phone_files", "event"),
    [
        *[(MAIN, None, None, "schedule")],
        *product([MAIN, *OTHER_REFS], ["both", "ua"], [value for value in PHONE_FILES if value], ["workflow_dispatch"]),
    ],
)
def test_the_checks_run_exactly_the_legs_their_build_ran(ref, data_environment, phone_files, event):
    """The dispatch passes the bake's own matrix rule as `data_environment`, and check-conditions.yml's matrix turns it
    back into the same legs: production only from main, never for a dispatch asking for UA alone or the dbt path."""
    ran = _bake_legs(ref, data_environment, phone_files, event)

    asked = _dispatched_legs(ref, data_environment, phone_files, event)

    assert asked in ("both", "ua")
    assert _checks_legs(ref, asked) == ran


def test_a_production_leg_from_another_ref_is_refused_by_bash_as_the_bake_refuses_it():
    """GitHub's `==` ignores case, so a branch called `Main` passes the matrix's rule; bash's `=` does not."""
    step = _step(CHECKS, "check", "Refuse a production leg from any ref but main")
    names = [each.get("name") for each in _steps(CHECKS, "check")]
    assert names.index(step["name"]) < names.index("Take the warehouse this leg's build handed off")
    for ref, expected in (("refs/heads/Main", 1), (MAIN, 0)):
        finished = subprocess.run(
            ["bash", "-e", "-c", step["run"]], env={"LEG": "production", "REF": ref, "PATH": "/usr/bin:/bin"}, check=False
        )
        assert finished.returncode == expected, ref


@pytest.mark.parametrize(("line", "runs", "code"), [("dbt", "true", 0), ("exporters", "false", 0), ("dbt # cutover", None, 1)])
def test_the_production_leg_runs_only_while_productions_hourly_leg_is_on_the_dbt_path(tmp_path, line, runs, code):
    """Read off publish-conditions.yml's PRODUCTION_PHONE_FILES line by its text, as extract-notices.yml reads it: a
    line in another shape stops the leg red rather than guessing."""
    step = _step(CHECKS, "check", "Check the production leg only while production's hourly leg is on the dbt path")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    text = BAKE.read_text(encoding="utf-8").replace(
        "  PRODUCTION_PHONE_FILES: exporters\n", f"  PRODUCTION_PHONE_FILES: {line}\n"
    )
    (workflows / BAKE.name).write_text(text, encoding="utf-8")
    output = tmp_path / "output"

    finished = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        env={"LEG": "production", "GITHUB_OUTPUT": str(output), "PATH": "/usr/bin:/bin"},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.returncode == code, finished.stdout
    assert (output.read_text().strip() if output.exists() else None) == (f"run={runs}" if runs else None)


@pytest.mark.parametrize("build_run", ["37800000001", "1; touch PWNED", "$(touch PWNED)", ""])
def test_only_a_run_id_reaches_the_steps_that_read_it(tmp_path, build_run):
    step = _step(CHECKS, "check", "Refuse a build_run that is not a run id")
    finished = subprocess.run(
        ["bash", "-e", "-c", step["run"]], env={"BUILD_RUN": build_run, "PATH": "/usr/bin:/bin"}, cwd=tmp_path, check=False
    )

    assert finished.returncode == (0 if build_run.isdigit() else 1)
    assert not (tmp_path / "PWNED").exists()
    assert _steps(CHECKS, "check")[0]["name"] == step["name"], "first, before any step reads it or a secret"


# --- the dispatch, in publish-conditions.yml ---------------------------------------------------------------------


def test_the_bake_starts_the_checks_after_both_legs_whatever_they_concluded_with_actions_write_on_that_job_alone():
    bake = _load(BAKE)
    job = bake["jobs"]["checks"]
    step = _step(BAKE, "checks", "Dispatch check-conditions.yml on this ref, with this run as its build_run")

    assert job["needs"] == "publish" and job["if"] == "${{ !cancelled() }}"
    assert bake["permissions"] == {"contents": "read"} and job["permissions"] == {"actions": "write"}
    assert [job_id for job_id, other in bake["jobs"].items() if "permissions" in other] == ["checks"]
    assert set(step["env"]) == {"GH_TOKEN", "REF", "BUILD_RUN", "LEGS"}
    assert step["env"]["BUILD_RUN"] == "${{ github.run_id }}" and step["env"]["REF"] == "${{ github.ref_name }}"
    assert "${{" not in step["run"]
    command = 'gh workflow run check-conditions.yml --repo "$GITHUB_REPOSITORY" --ref "$REF" -f "data_environment=$LEGS" -f "build_run=$BUILD_RUN"'
    assert command in step["run"]


def _run_the_dispatch(tmp_path: Path, ref: str, gh_exit: int = 0) -> tuple[int, str, list[list[str]]]:
    """The dispatch step's script, as GitHub runs it, with a stand-in `gh` that logs its argv and exits `gh_exit`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "gh.jsonl"
    stub = bin_dir / "gh"
    stub.write_text(
        "#!/usr/bin/env python3\nimport json, os, sys\n"
        "with open(os.environ['GH_LOG'], 'a') as log:\n    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"sys.exit({gh_exit})\n"
    )
    stub.chmod(0o755)
    summary = tmp_path / "summary.md"
    summary.write_text("")
    step = _step(BAKE, "checks", "Dispatch check-conditions.yml on this ref, with this run as its build_run")
    finished = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_LOG": str(log),
            "GH_TOKEN": "a-token-the-stand-in-ignores",
            "GITHUB_REPOSITORY": "OurHike/OurHike",
            "GITHUB_STEP_SUMMARY": str(summary),
            "BUILD_RUN": BUILD_RUN,
            "LEGS": "ua",
            "REF": ref,
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return finished.returncode, summary.read_text(), calls


@pytest.mark.parametrize("ref", ["main", "claude/it's;$(touch${IFS}PWNED)"])
def test_the_dispatch_starts_the_checks_of_this_run_and_its_summary_holds_the_command_that_does_it_again(tmp_path, ref):
    status, summary, calls = _run_the_dispatch(tmp_path, ref)

    expected = ["workflow", "run", "check-conditions.yml", "--repo", "OurHike/OurHike", "--ref", ref]
    expected += ["-f", "data_environment=ua", "-f", f"build_run={BUILD_RUN}"]
    assert status == 0 and calls == [expected]
    (command,) = [line for line in summary.splitlines() if line.startswith("gh workflow run ")]
    assert shlex.split(command)[1:] == expected
    assert not (tmp_path / "PWNED").exists()


def test_a_dispatch_that_fails_turns_only_its_own_job_red_and_leaves_the_command(tmp_path):
    status, summary, calls = _run_the_dispatch(tmp_path, "main", gh_exit=1)

    assert status != 0 and len(calls) == 1
    assert "gh workflow run check-conditions.yml" in summary and "This run dispatched" not in summary


# --- what the checks may touch ------------------------------------------------------------------------------------


def test_each_leg_shares_its_concurrency_group_with_the_bakes_leg_and_neither_takes_publish_data_for_it():
    """So the next hourly build of a leg waits for its checks instead of racing their history save, and a checks run is
    never an entrant that cancels a publisher queued in publish-data (#1513)."""
    checks, bake = _load(CHECKS), _load(BAKE)
    group = {"group": "conditions-history-${{ matrix.data_environment }}", "cancel-in-progress": False}

    assert checks["jobs"]["check"]["concurrency"] == group == bake["jobs"]["publish"]["concurrency"]
    assert "concurrency" not in checks, "a workflow-level group would hold both legs, and could not name the leg"
    assert bake["concurrency"]["group"] == "publish-data", "the bake's whole run still holds publish-data"


def test_the_one_object_the_checks_write_is_conditions_data_quality_json_after_the_checks_succeeded():
    steps = _steps(CHECKS, "check")
    publishing = [step for step in steps if "publish.py" in str(step.get("run", ""))]

    assert [step["run"].strip() for step in publishing] == ["python publish.py --sidecar conditions/data_quality.json"]
    (publish,) = publishing
    assert publish["if"] == "steps.checks.outcome == 'success'"
    assert (
        publish["env"]["OURHIKE_DATA_ENV"] == "${{ matrix.data_environment }}" and publish["env"]["OURHIKE_PHONE_FILES"] == "dbt"
    )
    names = [step.get("name") for step in steps]
    assert names.index("Run every check of the hourly lane, and write the data-quality file") < names.index(publish["name"])
    assert not [step for step in steps if "upload-artifact" in str(step.get("uses", ""))]


def test_the_warehouse_crosses_through_the_legs_history_store_the_build_and_its_checks_both_name():
    """hand_off.py says why not an Actions artifact. The store is the one the build restored from and saved to, which
    the checks run's build record must match (build_marts.py refuses another)."""
    store = '"s3://$R2_RAW_BUCKET/history/conditions_$ENVIRONMENT"'
    build = _step(BAKE, "publish", "Build the closures and warnings marts and their writers (dbt path)")["run"]
    hand_off = _step(BAKE, "publish", "Hand this build's warehouse to its checks (dbt path)")
    take = _step(CHECKS, "check", "Take the warehouse this leg's build handed off")["run"]
    checks = _step(CHECKS, "check", "Run every check of the hourly lane, and write the data-quality file")["run"]

    assert f"--history-url {store}" in build and f"--history-url {store}" in checks
    assert f"--url {store}" in hand_off["run"] and f"--url {store}" in take
    assert "hand_off.py put" in hand_off["run"] and "hand_off.py take" in take
    assert "--lane hourly --checks-only" in checks and "--history-on-failure degrade" in checks
    for workflow in (BAKE, CHECKS):
        assert not [
            step
            for job in _load(workflow)["jobs"].values()
            for step in job.get("steps") or []
            if "upload-artifact" in str(step.get("uses", ""))
        ], workflow.name


def test_the_checks_take_a_warehouse_only_from_the_commit_they_checked_out():
    """hand_off.py, "THE CHECKS RUN THE BUILD'S OWN COMMIT, OR NONE": the build records its commit, and the checks,
    dispatched on a branch whose newest commit a push may have moved, give theirs; both read through env."""
    hand_off = _step(BAKE, "publish", "Hand this build's warehouse to its checks (dbt path)")
    take = _step(CHECKS, "check", "Take the warehouse this leg's build handed off")
    checkout = [step for step in _steps(CHECKS, "check") if str(step.get("uses", "")).startswith("actions/checkout@")]

    assert hand_off["env"]["COMMIT"] == take["env"]["COMMIT"] == "${{ github.sha }}"
    assert '--commit "$COMMIT"' in hand_off["run"] and '--commit "$COMMIT"' in take["run"]
    assert len(checkout) == 1 and "with" not in checkout[0], "the checkout is github.sha, the commit the take compares"


def test_the_hand_off_follows_the_publish_red_or_green_and_never_turns_it_red():
    """publish.py exits 1 for a held source after uploading everything else, the hour the checks matter most; a failed
    hand-off is the checks' to report, never the publish's."""
    steps = _steps(BAKE, "publish")
    names = [step.get("name") for step in steps]
    hand_off = _step(BAKE, "publish", "Hand this build's warehouse to its checks (dbt path)")

    assert names.index(hand_off["name"]) == names.index("Publish to R2") + 1
    assert hand_off["continue-on-error"] is True
    assert "steps.build.outcome == 'success'" in hand_off["if"]
    assert "(steps.publish.outcome == 'success' || steps.publish.outcome == 'failure')" in hand_off["if"]
    assert _step(BAKE, "publish", "Publish to R2")["id"] == "publish"


# --- the hour -------------------------------------------------------------------------------------------------------

#: What publish-conditions.yml's cron, "40 * * * *", leaves between two runs, in minutes.
HOUR = 60


def test_a_build_and_its_checks_each_at_their_caps_still_end_inside_the_hour():
    """The bake's publish job, its dispatch job and a checks leg, one after the other, each at its timeout: so even a
    run whose every job ran to its cap is done before the next hour's build would wait on it (Reasoned from the caps;
    the measured times are far under them, build_marts.py's docstring)."""
    bake, checks = _load(BAKE)["jobs"], _load(CHECKS)["jobs"]
    total = bake["publish"]["timeout-minutes"] + bake["checks"]["timeout-minutes"] + checks["check"]["timeout-minutes"]

    assert total <= HOUR, total
    (run,) = [step for step in checks["check"]["steps"] if step.get("id") == "checks"]
    take = _step(CHECKS, "check", "Take the warehouse this leg's build handed off")
    assert run["timeout-minutes"] + take["timeout-minutes"] < checks["check"]["timeout-minutes"], "the job's cap holds both"
