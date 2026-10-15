"""check-conditions.yml's `parity` job: the six conditions files against today's exporters, every hour.

pipeline/ELT.md's open question 17, answered by the maintainer's poll of 2026-10-10: "Compare every soak hour". What is
held here is what keeps that comparison out of a hiker's way and honest about what it compared:
- the extract keeps the hour's answers, and publish-conditions.yml's hand-off step puts them, after the warehouse and
  without touching its status, in the leg's private history store;
- the comparison runs in check-conditions.yml, beside the checks and on exactly their legs, and in no job of
  publish-conditions.yml, every one of which holds publish-data until its run ends (#1513 - A queued publish is
  silently cancelled when another one joins publish-data, and it looks like a green build);
- it takes the bundle of its build run and this commit alone, and a bundle that does not come is an hour not compared,
  never a red run;
- the one artifact either workflow uploads is the comparison's result, keys and changed fields only, never the bundle;
- it holds no key to the bucket hikers download from, and fits beside the checks.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
BAKE = WORKFLOWS / "publish-conditions.yml"
CHECKS = WORKFLOWS / "check-conditions.yml"
STORE = '"s3://$R2_RAW_BUCKET/history/conditions_$ENVIRONMENT"'
HAND_OFF = "Hand this build's warehouse to its checks (dbt path)"
EXTRACT = "Extract this leg's closures and warnings into the raw store (dbt path)"
WANTED = "Check the production leg only while production's hourly leg is on the dbt path"
TAKE = "Take the comparison bundle this leg's build handed off"
TAKE_WAREHOUSE = "Take the warehouse this leg's build handed off"
COMPARE = "Compare the six conditions files with today's exporters"
UPLOAD = "Upload this hour's comparison, keys and changed fields only"
BUILD_RUN = "38075292380"


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _job(path: Path, name: str) -> dict:
    return _workflow(path)["jobs"][name]


def _step(path: Path, job: str, name: str) -> dict:
    (step,) = [step for step in _job(path, job)["steps"] if step.get("name") == name]
    return step


# --- where it runs ------------------------------------------------------------------------------------------------


def test_the_comparison_runs_beside_the_checks_and_in_no_job_that_holds_publish_data():
    """Every job of publish-conditions.yml keeps publish-data held until its run ends, and a publisher queued behind it
    is the one a third entrant cancels with nothing red (#1513). Beside `check`, never after it, so neither waits on
    the other, and with no group of its own: two runs of a leg take two builds' bundles and share nothing they write."""
    parity, checks, bake = _job(CHECKS, "parity"), _workflow(CHECKS), _workflow(BAKE)

    assert not {"needs", "if", "concurrency", "permissions"} & set(parity), sorted(parity)
    assert "concurrency" not in checks and checks["permissions"] == {"contents": "read"}
    assert "parity" not in bake["jobs"]
    assert "hourly_parity.py compare" not in json.dumps(bake), "no job of the bake compares"


def test_the_comparison_runs_exactly_the_checks_legs_with_their_own_first_four_steps():
    """The matrix, its two locks on the production leg, the build_run refused unless it is a run id, and production
    run only while its hourly leg is on the dbt path: `check`'s own, word for word, which test_check_conditions.py
    runs for every trigger, ref and input."""
    parity, check = _job(CHECKS, "parity"), _job(CHECKS, "check")

    assert parity["strategy"] == check["strategy"]
    assert parity["steps"][:4] == check["steps"][:4]
    assert [step.get("name") or step.get("uses") for step in parity["steps"][:4]] == [
        "Refuse a build_run that is not a run id",
        "Refuse a production leg from any ref but main",
        "actions/checkout@v7",
        WANTED,
    ]


def test_every_step_after_the_choice_runs_only_for_a_leg_the_checks_run():
    steps = _job(CHECKS, "parity")["steps"]
    after = steps[[step.get("name") for step in steps].index(WANTED) + 1 :]

    assert after, "the comparison's own steps follow the choice"
    for step in after:
        assert "steps.wanted.outputs.run == 'true'" in str(step.get("if")), step.get("name") or step.get("uses")


# --- the answers, kept and handed on --------------------------------------------------------------------------------


def test_the_extract_keeps_the_hours_answers_where_the_hand_off_bundles_them_from():
    extract = _step(BAKE, "publish", EXTRACT)["run"]
    hand_off = _step(BAKE, "publish", HAND_OFF)["run"]

    assert "--record-answers data/hourly_parity/answers" in extract
    assert "hourly_parity.py bundle --answers data/hourly_parity/answers" in hand_off
    assert "--processed data/processed/dbt --out data/hourly_parity/bundle" in hand_off
    assert f"--url {STORE}" in hand_off and "--bundle data/hourly_parity/bundle" in hand_off


def _run_the_hand_off(
    tmp_path: Path, codes: dict[str, int], *, spent: int = 0, sleeps: dict[str, float] | None = None
) -> tuple[int, list[str], str]:
    """The hand-off step's script with a stand-in for the extract venv's python that logs its first two arguments,
    sleeps and exits as `sleeps` and `codes` say for them; `spent` seconds of the step's minute already gone when the
    warehouse's put starts. Returns the exit, the calls and the output."""
    python = tmp_path / "extract" / "bin" / "python"
    python.parent.mkdir(parents=True)
    log = tmp_path / "calls"
    log.write_text("")
    python.write_text(
        "#!/usr/bin/env python3\nimport json, os, sys, time\n"
        "name = sys.argv[1] + ' ' + sys.argv[2]\n"
        "open(os.environ['CALLS'], 'a').write(name + '\\n')\n"
        f"time.sleep(json.loads({json.dumps(json.dumps(sleeps or {}))}).get(name, 0))\n"
        f"sys.exit(json.loads({json.dumps(json.dumps(codes))}).get(name, 0))\n"
    )
    python.chmod(0o755)
    script = _step(BAKE, "publish", HAND_OFF)["run"]
    assert "started=$SECONDS" in script, "the bundle's share of the minute is counted from the step's start"
    finished = subprocess.run(
        ["bash", "-e", "-c", script.replace("started=$SECONDS", f"started=$((SECONDS - {spent}))")],
        env={**os.environ, "RUNNER_TEMP": str(tmp_path), "CALLS": str(log), "R2_RAW_BUCKET": "raw", "ENVIRONMENT": "ua"}
        | {"RUN": BUILD_RUN, "ATTEMPT": "1", "COMMIT": "e49ca601"},
        capture_output=True,
        text=True,
    )
    return finished.returncode, log.read_text().splitlines(), finished.stdout


EVERY_CALL = ["hand_off.py put", "hourly_parity.py bundle", "hand_off.py put-bundle"]


@pytest.mark.parametrize(
    ("codes", "status", "calls"),
    [
        ({}, 0, EVERY_CALL),
        ({"hand_off.py put": 1}, 1, EVERY_CALL),
        ({"hand_off.py put-bundle": 1}, 0, EVERY_CALL),
        ({"hourly_parity.py bundle": 1}, 0, EVERY_CALL[:2]),
        ({"hand_off.py put": 1, "hand_off.py put-bundle": 1}, 1, EVERY_CALL),
    ],
)
def test_the_hand_off_puts_the_warehouse_first_and_its_status_alone_decides_the_step(tmp_path, codes, status, calls):
    """The checks' hand-off keeps every second it had, and a bundle that fails never turns the step red, nor one that
    succeeds hide a warehouse that did not move. A bundle that could not be gathered is not put, so the store keeps
    the last run's, which take-bundle refuses as another run's."""
    code, called, _ = _run_the_hand_off(tmp_path, codes)

    assert called == calls
    assert code == status


def test_a_warehouse_hand_off_that_leaves_the_bundle_too_little_of_the_minute_puts_no_bundle_and_says_so(tmp_path):
    code, calls, out = _run_the_hand_off(tmp_path, {}, spent=47)

    assert (code, calls) == (0, ["hand_off.py put"])
    # 47 s or a little more: the stand-in's own start counts too, on a loaded machine.
    assert re.search(r"::warning title=Comparison bundle not moved::the warehouse's hand-off took (4[7-9]|50) s", out), out


def test_a_bundle_that_outruns_what_the_minute_left_is_stopped_and_the_warehouses_status_still_decides(tmp_path):
    """50 - 42 = 8 s left, or a few fewer on a loaded machine: the bundle sleeps past it, `timeout` stops it,
    put-bundle never runs, and the step keeps the warehouse's exit rather than running into its cap."""
    code, calls, out = _run_the_hand_off(tmp_path, {}, spent=42, sleeps={"hourly_parity.py bundle": 30})

    assert (code, calls) == (0, EVERY_CALL[:2])
    assert re.search(r"::warning title=Comparison bundle not moved::the bundle did not move in the [5-8] s", out), out


# --- the take and the comparison ------------------------------------------------------------------------------------


def test_the_comparison_takes_the_bundle_of_its_build_run_on_this_commit_as_the_checks_take_the_warehouse():
    take, warehouse = _step(CHECKS, "parity", TAKE), _step(CHECKS, "check", TAKE_WAREHOUSE)

    assert f"hand_off.py take-bundle --url {STORE}" in take["run"] and '"$RUNNER_TEMP/extract/bin/python"' in take["run"]
    assert '--run "$BUILD_RUN"' in take["run"] and '--commit "$COMMIT"' in take["run"]
    assert "--out data/hourly_parity/bundle" in take["run"]
    for name in ("ENVIRONMENT", "BUILD_RUN", "COMMIT"):
        assert take["env"][name] == warehouse["env"][name], name
    assert take["env"]["BUILD_RUN"] == "${{ inputs.build_run }}" and take["env"]["COMMIT"] == "${{ github.sha }}"


def _run_a_step(tmp_path: Path, step: dict, env: dict[str, str], program: str, code: int = 0) -> tuple[int, list, str]:
    """`step`'s script, with `program` standing in on PATH and at $RUNNER_TEMP/extract/bin/python: it logs its argv
    and exits `code`. Returns the step's exit, the argv each call got, and what the step wrote to $GITHUB_OUTPUT."""
    log, output = tmp_path / "argv.jsonl", tmp_path / "github_output"
    log.write_text("")
    output.write_text("")
    stub = "#!/usr/bin/env python3\nimport json, os, sys\n"
    stub += "open(os.environ['ARGV_LOG'], 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
    stub += f"sys.exit({code})\n"
    for path in (tmp_path / "bin" / program, tmp_path / "extract" / "bin" / "python"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stub)
        path.chmod(0o755)
    finished = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        env={
            **os.environ,
            "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(tmp_path),
            "ARGV_LOG": str(log),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            "GITHUB_RUN_ID": "38075301234",
        }
        | env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    return finished.returncode, calls, output.read_text()


@pytest.mark.parametrize(("code", "taken"), [(0, "true"), (4, "false"), (1, "false")])
def test_a_bundle_that_cannot_be_taken_is_an_hour_not_compared_never_a_red_step(tmp_path, code, taken):
    """take-bundle's exit 4 is another run's bundle, or another commit's, or none; 1 is a store that could not be
    read or a torn upload. Either costs this hour its comparison, which the compare step then says, and nothing else."""
    env = {"ENVIRONMENT": "ua", "BUILD_RUN": BUILD_RUN, "COMMIT": "e49ca601", "R2_RAW_BUCKET": "raw"}
    status, calls, output = _run_a_step(tmp_path, _step(CHECKS, "parity", TAKE), env, "python", code)

    assert status == 0 and output == f"taken={taken}\n"
    assert calls == [
        ["hand_off.py", "take-bundle", "--url", "s3://raw/history/conditions_ua", "--out", "data/hourly_parity/bundle"]
        + ["--run", BUILD_RUN, "--commit", "e49ca601"]
    ]


def test_the_compare_step_runs_after_a_take_that_failed_or_timed_out_so_the_hour_is_recorded():
    """A take step killed at its 2-minute cap fails, and an `if:` with no status function carries an implicit
    success(), so the compare step was skipped and the hour left no run.json: the gate read it as a run that never came,
    which decision 158's gap rule absorbs (the 2026-10-15 review's finding S2-3). With !cancelled() it runs, finds
    TAKEN empty, and writes every family not compared; the upload keeps that whatever the compare step's outcome."""
    compare, upload = _step(CHECKS, "parity", COMPARE), _step(CHECKS, "parity", UPLOAD)

    assert "!cancelled()" in compare["if"] and "steps.wanted.outputs.run == 'true'" in compare["if"]
    assert "steps.take" not in compare["if"], "the take's outcome reaches the step as TAKEN, never as a reason to skip"
    assert "steps.compare.outcome == 'success' || steps.compare.outcome == 'failure'" in upload["if"]


@pytest.mark.parametrize("taken", ["true", "false", ""])
def test_the_compare_step_names_the_build_and_says_when_no_bundle_came(tmp_path, taken):
    """An empty TAKEN is a take step that never ran: no bundle came, said, as for one that was not taken."""
    env = {"LEG": "ua", "BUILD_RUN": BUILD_RUN, "COMMIT": "e49ca601", "TAKEN": taken}
    status, calls, _ = _run_a_step(tmp_path, _step(CHECKS, "parity", COMPARE), env, "python")

    assert status == 0
    (argv,) = calls
    assert argv[:6] == [
        "hourly_parity.py",
        "compare",
        "--bundle",
        "data/hourly_parity/bundle",
        "--out",
        "data/hourly_parity/result",
    ]
    named = dict(zip(argv[6::2], argv[7::2], strict=False))
    assert {key: named[key] for key in ("--run", "--commit", "--leg", "--compared-in")} == {
        "--run": BUILD_RUN,
        "--commit": "e49ca601",
        "--leg": "ua",
        "--compared-in": "38075301234",
    }
    assert named["--extract-python"] == f"{tmp_path}/extract/bin/python"
    assert ("--missing" in argv) == (taken != "true")


def test_the_one_artifact_either_workflow_uploads_is_the_comparisons_keys_only_result():
    """hand_off.py's "NOT AN ACTIONS ARTIFACT": the bundle and the warehouse hold records, OurHike's reports among them,
    and an artifact of a public repository is anyone's to download. The result holds keys and changed fields alone."""
    uploads = [
        (path.name, job_id, step)
        for path in (BAKE, CHECKS)
        for job_id, job in _workflow(path)["jobs"].items()
        for step in job.get("steps") or []
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
    ]

    assert [(name, job_id, step["name"]) for name, job_id, step in uploads] == [("check-conditions.yml", "parity", UPLOAD)]
    (_, _, upload) = uploads[0]
    assert upload["with"]["path"] == "pipeline/data/hourly_parity/result/"
    assert upload["with"]["name"] == "hourly-parity-${{ matrix.data_environment }}"
    assert "steps.compare.outcome == 'failure'" in upload["if"], "a red comparison is the one most worth keeping"
    assert not re.search(r"hourly_parity/(bundle|answers)|warehouse", json.dumps(upload["with"]))


def test_the_comparison_holds_no_key_to_the_bucket_hikers_download_from():
    parity = json.dumps(_job(CHECKS, "parity"))

    assert set(re.findall(r"secrets\.([A-Z0-9_]+)", parity)) == {
        "R2_RAW_BUCKET",
        "R2_RAW_ACCESS_KEY_ID",
        "R2_RAW_SECRET_ACCESS_KEY",
        "R2_ENDPOINT_URL",
    }
    assert "publish.py" not in parity and "R2_WRITE_ENABLED" not in parity


def test_the_comparison_fits_beside_the_checks_and_its_steps_inside_its_cap():
    """Beside `check`, under its cap, so test_check_conditions.py's sum of a build and its checks at their caps still
    ends inside the hour."""
    parity, check = _job(CHECKS, "parity"), _job(CHECKS, "check")

    assert parity["timeout-minutes"] <= check["timeout-minutes"]
    caps = [step["timeout-minutes"] for step in parity["steps"] if "timeout-minutes" in step]
    assert sum(caps) < parity["timeout-minutes"], caps
