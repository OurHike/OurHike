"""refresh-reference.yml, the monthly lane's scheduled half: it extracts, pins and starts the build, nothing in it can
reach production, and each job holds only its own keys.

pipeline/ELT.md, "Why a scheduled run cannot reach production", lists the
locks: no input names an environment, the one publish writes UA's keys by a
literal, and promotion is the release train's. Since the maintainer's choice B
(poll, 2026-10-08) the lane is two workflows: this one extracts every monthly
resource, pins the raw inputs and dispatches build-reference.yml by name with
the pinned raw_run, and that one builds from the pin and publishes
(test_build_reference.py holds that half). This file holds what a workflow
file can hold of this half: its schedule, the one-run-at-a-time group, dlt's
telemetry off, which job holds which step down to the pin, the dispatch's one
permission, its ref and its raw_run, and the `refused` job.

It also holds ELT.md's new assertion for every scheduled workflow that
publishes ("Repository tests a new workflow must satisfy"): each names UA as
a literal, in its own publish steps and in those of a workflow it dispatches,
and publish-conditions.yml's production leg is the one exemption.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
NAME = "refresh-reference.yml"
#: The workflow this one's dispatch job starts with the pinned raw_run.
BUILD = "build-reference.yml"
PUBLIC_BUCKET_SECRETS = {"R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}
RAW_STORE_SECRETS = {"R2_RAW_BUCKET", "R2_RAW_ACCESS_KEY_ID", "R2_RAW_SECRET_ACCESS_KEY"}
SECRET = re.compile(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)")
#: `gh workflow run <file>`: a workflow another one starts by file name.
DISPATCH = re.compile(r"\bgh workflow run ([\w.-]+\.ya?ml)\b")
# The scheduled publishers that write production, each with why: publish-conditions.yml
# bakes conditions/ for both environments hourly, outside every release folder, because
# "a closure that has reopened must stop being served" (pipeline/DATA_RELEASES.md:274;
# ELT.md, "The conditions bake keeps publishing straight to production").
PRODUCTION_ON_A_SCHEDULE = {"publish-conditions.yml"}
#: The run id the extract job hands on: extract/_run.py stamps it with "%Y%m%dT%H%M%S.%fZ".
RAW_RUN = "20261008T041936.333353Z"
#: Every step the build job ran down to the pin before choice B, now the pin job's, by name.
PIN_STEPS = [
    "Is this raw_run pinned already",
    "Today's fetchers' files for this raw_run, and the DEM tile index",
    "OSM's Geofabrik extracts and the last landed water scans, from the raw store",
    "Scan the extracts for water (fetch_osm_water.py, fetch_trail_water.py --derive)",
    "Say which water scans this build lands",
    "Pin this run's raw inputs",
]
# fetch_trail_water.ELEVATION_CACHE_PATH and export_elevation.SAMPLE_CACHE_PATH, workspace-relative: the EPQS answers
# step_osm_water_grade.py and fetch_trail_water.py --derive ask through, and the DEM per-point cache beside the tile
# index step_dem_sampling.py samples from. pipeline/tests/test_fetch_cache_paths.py holds them to the constants.
ELEVATION_ANSWERS = {"pipeline/data/raw/epqs_elevations.json", "pipeline/data/raw/elevation/samples.json"}
#: How GitHub runs a `run:` step whose job names no shell.
BASH = ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c"]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True.
    return workflow.get("on") or workflow.get(True) or {}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return _load(WORKFLOWS / NAME)


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _secrets(job: dict) -> set[str]:
    return {name for text in _strings(job) for name in SECRET.findall(text)}


def _runs(job: dict) -> str:
    return "\n".join(str(step.get("run") or "") for step in job.get("steps") or [])


def _first_step(steps: list[dict], text: str) -> int:
    found = [index for index, step in enumerate(steps) if text in (step.get("run") or "")]
    assert found, f"no step runs {text!r}"
    return found[0]


def _cached_paths(step: dict, env: dict) -> set[str]:
    path = str((step.get("with") or {}).get("path", ""))
    for name, value in env.items():
        path = path.replace("${{ env.%s }}" % name, str(value))
    return {line.strip() for line in path.splitlines() if line.strip()}


def _cache_steps(job: dict, workflow: dict, kind: str) -> list[int]:
    """The indexes of the job's actions/cache/<kind> steps over the EPQS answers and the DEM samples."""
    env = {**workflow["env"], **(job.get("env") or {})}
    return [
        index
        for index, step in enumerate(job["steps"])
        if str(step.get("uses", "")).startswith(f"actions/cache/{kind}") and _cached_paths(step, env) == ELEVATION_ANSWERS
    ]


def _dispatched(workflow: dict) -> set[str]:
    return {name for job in (workflow.get("jobs") or {}).values() for name in DISPATCH.findall(_runs(job))}


def test_it_runs_at_05_15_utc_on_the_3rd_and_on_a_dispatch_that_takes_no_input(workflow):
    triggers = _triggers(workflow)

    assert triggers["schedule"] == [{"cron": "15 5 3 * *"}], "ELT.md, 'The schedule: 05:15 UTC on the 3rd'"
    assert "workflow_dispatch" in triggers
    assert not (triggers["workflow_dispatch"] or {}).get("inputs"), "an input could name an environment"
    assert set(triggers) == {"schedule", "workflow_dispatch"}, "never a push or a pull request"


def test_nothing_in_it_reads_an_input_or_names_any_environment_but_ua(workflow):
    text = (WORKFLOWS / NAME).read_text(encoding="utf-8")
    values = _strings(workflow["jobs"])

    assert "inputs." not in text and "data_environment" not in "\n".join(values)
    assert not [value for value in values if "production" in value], "no value in the file may name production"
    for job_id, job in workflow["jobs"].items():
        assert job.get("environment") in (None, "ua"), f"{job_id}'s environment is {job.get('environment')!r}"
        for step in job.get("steps") or []:
            if "OURHIKE_DATA_ENV" in (step.get("env") or {}):
                assert step["env"]["OURHIKE_DATA_ENV"] == "ua", f"{job_id}: {step.get('name')}"


def test_its_four_jobs_are_the_extract_the_pin_the_dispatch_and_refused(workflow):
    """Choice B: the build, publish, confirm and parity jobs are build-reference.yml's, started by the dispatch."""
    assert list(workflow["jobs"]) == ["extract", "pin", "dispatch", "refused"]
    assert not {"build", "publish", "confirm", "parity", "parity-report"} & set(workflow["jobs"])


def test_no_job_holds_the_public_buckets_keys_or_the_write_switch(workflow):
    """The publish is build-reference.yml's job, and the only one there that holds them."""
    for job_id, job in workflow["jobs"].items():
        holds = _secrets(job) & PUBLIC_BUCKET_SECRETS
        assert not holds and "R2_WRITE_ENABLED" not in yaml.safe_dump(job), f"{job_id} holds {sorted(holds)}"


def test_the_extract_job_holds_the_raw_store_and_the_upstream_credentials_and_nothing_else(workflow):
    # The two upstream credentials: Hike Finder's password, and the NPS Data API's key for decision 54's NPS places
    # and campgrounds (extract/_ogc.py's JsonFeatures), both optional and both warned about when unset.
    upstream = {"HIKEFINDER_PASSWORD", "NPS_API_KEY"}
    assert _secrets(workflow["jobs"]["extract"]) == RAW_STORE_SECRETS | {"R2_ENDPOINT_URL"} | upstream


def test_the_pin_job_holds_the_raw_store_and_nothing_else_and_the_others_hold_no_secret(workflow):
    assert _secrets(workflow["jobs"]["pin"]) == RAW_STORE_SECRETS | {"R2_ENDPOINT_URL"}
    assert not _secrets(workflow["jobs"]["dispatch"]) and not _secrets(workflow["jobs"]["refused"])


@pytest.mark.parametrize("job_id", ["extract", "pin"])
def test_a_job_holding_the_raw_store_key_names_every_raw_secret_before_it_uses_one(workflow, job_id):
    steps = workflow["jobs"][job_id]["steps"]
    first = next(index for index, step in enumerate(steps) if _secrets(step))
    check = steps[first]

    assert "missing" in (check.get("run") or ""), f"{job_id}'s first step holding a secret is not the check"
    for name in sorted(RAW_STORE_SECRETS | {"R2_ENDPOINT_URL"}):
        assert name in check["run"] and name in (check.get("env") or {}), f"{job_id} does not check {name} by name"


def test_one_run_at_a_time_and_a_queued_run_is_never_cancelled_by_a_running_one(workflow):
    assert workflow["concurrency"] == {"group": "raw-lake-monthly", "cancel-in-progress": False}


def test_dlt_and_dbt_telemetry_are_off_for_every_job(workflow):
    assert workflow["env"]["RUNTIME__DLTHUB_TELEMETRY"] == "false"
    assert workflow["env"]["DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS"] == "false"
    for job_id, job in workflow["jobs"].items():
        assert "RUNTIME__DLTHUB_TELEMETRY" not in (job.get("env") or {}), f"{job_id} overrides it"


def test_the_extract_runs_the_monthly_lane_with_its_as_landed_copy_and_cross_lane_inputs(workflow):
    runs = _runs(workflow["jobs"]["extract"])

    assert "-m extract._run --lane monthly" in runs
    assert "--as-landed" in runs and "--cross-lane-inputs" in runs and "--report-json" in runs
    # Only this run normalizes on several processes; fixture mode and the tests keep one (_run.py says why).
    assert "--normalize-workers 4" in runs


def test_a_layer_refused_on_its_own_lets_the_pin_and_the_dispatch_run_and_the_last_job_go_red(workflow):
    """Monthly runs 10, 11, 12, 14 and 15 each stopped on one layer; extract/_run.py's ISOLATING_LANES now exits 3.
    `refused` waits on this file's jobs alone: the build it would once have waited on is build-reference.yml's run."""
    extract = workflow["jobs"]["extract"]
    (step,) = [step for step in extract["steps"] if step.get("id") == "extract"]
    assert '"$status" -eq 3' in step["run"] and "partial=true" in step["run"]
    assert '--summary "$GITHUB_STEP_SUMMARY"' in step["run"], "the summary names each refused layer"
    assert extract["outputs"]["partial"] == "${{ steps.extract.outputs.partial }}"

    refused = workflow["jobs"]["refused"]
    assert refused["if"] == "always() && needs.extract.outputs.partial == 'true'"
    assert set(refused["needs"]) == set(workflow["jobs"]) - {"refused"}, "after every other job"
    assert not _secrets(refused) and "exit 1" in _runs(refused)
    for job_id in ("pin", "dispatch"):
        assert "if" not in workflow["jobs"][job_id], f"{job_id} must run after a partial extract, which exits 0"


def test_the_pin_job_holds_every_step_the_build_ran_down_to_the_pin_and_no_dbt(workflow):
    """Choice B moved them whole, in order; build-reference.yml's build job starts at "Build the warehouse from the
    pin" and holds none of them (test_build_reference.py)."""
    job = workflow["jobs"]["pin"]
    names = [step.get("name") for step in job["steps"]]
    held = [name for name in names if name in PIN_STEPS]
    runs = _runs(job)

    assert held == PIN_STEPS
    assert job["needs"] == "extract" and job["env"]["RAW_RUN"] == "${{ needs.extract.outputs.raw_run }}"
    assert "requirements-dbt.txt" not in yaml.safe_dump(job) and "generate_dbt.py" not in runs
    assert not re.search(r"\bdbt\"?\s+(deps|build|run|seed|test|parse)\b", runs), "no dbt command runs before the pin"
    assert "build_marts.py" not in runs and "--warehouse" not in runs, "the warehouse is build-reference.yml's to build"


def test_the_pin_job_pins_and_writes_only_under_steps(workflow):
    runs = _runs(workflow["jobs"]["pin"])

    assert "extract._run" not in runs, "the pin job never extracts, so it never writes the raw store's raw/"
    for match in re.finditer(r'--steps-url "([^"]+)"', runs):
        assert match.group(1) == "s3://$R2_RAW_BUCKET/steps", match.group(0)
    assert "extract._warehouse pin " in runs and "extract._warehouse store" not in runs


def test_the_pin_job_scans_osm_water_from_the_raw_stores_extracts_before_the_pin_that_build_marts_reads(workflow):
    """#1652 - Download OSM's Geofabrik extracts at most once a month, into a private raw bucket that outlives the
    7-day Actions cache. The copies come down after today's fetchers' files (fetch_trail_water.py --derive reads ATC's
    sites from the as-landed copy), both scans run over them before the pin, the pin carries the scans, and
    build-reference.yml's build_marts.py lands them from the pin through the warehouse step's materialised files."""
    steps = workflow["jobs"]["pin"]["steps"]
    as_landed = _first_step(steps, "extract._warehouse as-landed")
    pull = _first_step(steps, "-m extract._geofabrik pull")
    osm = _first_step(steps, "fetch_osm_water.py")
    site = _first_step(steps, "fetch_trail_water.py --derive")
    landed = _first_step(steps, "-m extract._geofabrik landed")
    pin = _first_step(steps, "extract._warehouse pin ")

    assert as_landed < pull < osm == site < landed < pin
    # extract/_geofabrik.py's SCANS: each scan pinned under derived/, never at its scanner's own path.
    for pinned, local in {
        "derived/osm_water.geojson": "osm_water.geojson",
        "derived/trail_water.json": "trail_water.json",
    }.items():
        assert f"--extra {pinned}=data/raw/{local}" in steps[pin]["run"], pinned


def test_the_water_scans_run_only_on_a_complete_set_never_fail_the_pin_and_free_the_disk(workflow):
    """A missing or unreadable copy lands the last landed scans rather than a scan of part of the corridor, and a scan
    that refuses or crashes leaves them standing: neither may stop the pin, or the build after it."""
    steps = workflow["jobs"]["pin"]["steps"]
    pull = steps[_first_step(steps, "-m extract._geofabrik pull")]
    scan = steps[_first_step(steps, "fetch_osm_water.py")]
    landed = steps[_first_step(steps, "-m extract._geofabrik landed")]

    assert pull["id"] == "osm" and '--github-output "$GITHUB_OUTPUT"' in pull["run"] and "$GITHUB_STEP_SUMMARY" in pull["run"]
    assert "steps.osm.outputs.extracts == 'complete'" in scan["if"]
    assert scan["continue-on-error"] is True and isinstance(scan.get("timeout-minutes"), int)
    assert "rm -f data/raw/osm/*-latest.osm.pbf" in scan["run"] and "rm -f data/raw/osm/*-latest.osm.pbf" in landed["run"]
    assert "always()" in landed["if"] and "$GITHUB_STEP_SUMMARY" in landed["run"]
    assert not _secrets(scan) and not _secrets(landed), "the scans read files on disk and public hosts, no store"


def test_every_step_down_to_the_pin_is_skipped_on_a_rerun_that_already_has_one(workflow):
    """A rerun of the pin job on a raw_run already pinned goes straight on to the dispatch."""
    steps = workflow["jobs"]["pin"]["steps"]
    check = next(index for index, step in enumerate(steps) if step.get("id") == "pinned")
    pin = _first_step(steps, "extract._warehouse pin ")

    assert "extract._warehouse has-pin" in steps[check]["run"]
    for step in steps[check + 1 : pin + 1]:
        assert "steps.pinned.outputs.pinned" in step.get("if", ""), step.get("name")
    for step in steps[pin + 1 :]:
        assert str(step.get("uses", "")).startswith("actions/cache/save"), f"{step.get('name')} runs after the pin"
    assert workflow["jobs"]["dispatch"]["needs"] == ["extract", "pin"] and "if" not in workflow["jobs"]["dispatch"]


def test_the_pin_job_restores_the_epqs_answers_before_the_scan_that_asks_and_saves_them_for_the_build(workflow):
    """ARC-3 of PR #1805's second review carried the EPQS answers and the DEM samples between attempts in one job.
    fetch_trail_water.py --derive asks EPQS through the first file, so the pin job restores before it and saves after,
    also on a failed run, under the prefix build-reference.yml's build job restores (test_build_reference.py holds
    the two files to one prefix and one path list)."""
    job = workflow["jobs"]["pin"]
    steps = job["steps"]
    (restore,) = _cache_steps(job, workflow, "restore")
    (save,) = _cache_steps(job, workflow, "save")

    assert restore < _first_step(steps, "fetch_trail_water.py --derive") < _first_step(steps, "extract._warehouse pin ") < save
    assert "always()" in str(steps[save]["if"]) and steps[save]["continue-on-error"] is True
    prefix = str(steps[save]["with"]["key"]).split("${{")[0]
    assert prefix == "monthly-elevation-answers-" and str(steps[restore]["with"]["restore-keys"]).strip() == prefix


def test_the_dispatch_job_alone_holds_actions_write_and_hands_the_build_this_runs_ref_and_raw_run(workflow):
    """workflow_dispatch is the event a GITHUB_TOKEN may start a run with ("workflow_dispatch and repository_dispatch
    events always create workflow runs", GitHub's docs), and the dispatch endpoint needs `actions: write`. Everything
    the dispatched text is made of reaches the script through env, as test_run_steps_take_inputs_through_env.py
    requires of every run step."""
    job = workflow["jobs"]["dispatch"]
    (step,) = [step for step in job["steps"] if "gh workflow run" in (step.get("run") or "")]

    assert workflow["permissions"] == {"contents": "read"}
    assert job["permissions"] == {"actions": "write"}
    assert [job_id for job_id, other in workflow["jobs"].items() if "permissions" in other] == ["dispatch"]
    assert step["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "RAW_RUN": "${{ needs.extract.outputs.raw_run }}",
        "REF": "${{ github.ref_name }}",
    }
    assert 'gh workflow run build-reference.yml --repo "$GITHUB_REPOSITORY" --ref "$REF" -f "raw_run=$RAW_RUN"' in step["run"]
    assert "${{" not in step["run"]
    assert _dispatched(workflow) == {BUILD} and (WORKFLOWS / BUILD).is_file()


def _dispatch_step(workflow: dict) -> dict:
    (step,) = [step for step in workflow["jobs"]["dispatch"]["steps"] if "gh workflow run" in (step.get("run") or "")]
    return step


def _run_the_dispatch(workflow: dict, tmp_path: Path, ref: str, gh_exit: int = 0) -> tuple[int, str, list[list[str]]]:
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
    completed = subprocess.run(
        [*BASH, _dispatch_step(workflow)["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_LOG": str(log),
            "GH_TOKEN": "a-token-the-stand-in-ignores",
            "GITHUB_REPOSITORY": "OurHike/OurHike",
            "GITHUB_STEP_SUMMARY": str(summary),
            "RAW_RUN": RAW_RUN,
            "REF": ref,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return completed.returncode, summary.read_text(), calls


def test_the_dispatch_starts_build_reference_on_this_ref_with_this_raw_run_and_its_summary_says_how_again(workflow, tmp_path):
    """The brief for choice B: each extract run's summary prints the raw_run and the exact command that builds from
    it again. That command, run as printed, makes the same call the job made."""
    status, summary, calls = _run_the_dispatch(workflow, tmp_path, "main")

    expected = ["workflow", "run", BUILD, "--repo", "OurHike/OurHike", "--ref", "main", "-f", f"raw_run={RAW_RUN}"]
    assert status == 0 and calls == [expected]
    assert f"raw_run `{RAW_RUN}` is pinned" in summary
    (command,) = [line for line in summary.splitlines() if line.startswith("gh workflow run ")]
    assert command == f"gh workflow run {BUILD} --repo OurHike/OurHike --ref main -f raw_run={RAW_RUN}"
    assert shlex.split(command)[1:] == expected
    assert "This run dispatched build-reference.yml on `main`" in summary


def test_the_rebuild_command_stays_one_command_whatever_the_branch_is_called(workflow, tmp_path):
    """git allows a quote, a semicolon and `$(...)` in a branch name (`git check-ref-format --branch` accepts this
    one), so the printed command quotes each word (printf %q) and reads back as the same argv, never as a second
    command."""
    ref = "claude/it's;$(touch${IFS}PWNED)"
    status, summary, calls = _run_the_dispatch(workflow, tmp_path, ref)

    assert status == 0 and calls[0][calls[0].index("--ref") + 1] == ref
    (command,) = [line for line in summary.splitlines() if line.startswith("gh workflow run ")]
    assert shlex.split(command)[1:] == calls[0]
    assert not (tmp_path / "PWNED").exists()


def test_a_dispatch_that_fails_turns_the_job_red_and_leaves_the_command_to_run_by_hand(workflow, tmp_path):
    """Until a build-reference.yml is on the default branch GitHub refuses the dispatch (the workflow's comment):
    the job goes red, and the summary still holds the command, with no line claiming the build was started."""
    status, summary, calls = _run_the_dispatch(workflow, tmp_path, "main", gh_exit=1)

    assert status != 0 and len(calls) == 1
    assert f"gh workflow run {BUILD} --repo OurHike/OurHike --ref main -f raw_run={RAW_RUN}" in summary
    assert "This run dispatched" not in summary


def _publishes(job: dict) -> list[dict]:
    return [step for step in job.get("steps") or [] if "python publish.py" in (str(step.get("run") or "")).splitlines()]


def test_every_scheduled_workflow_that_publishes_names_ua_as_a_literal():
    """ELT.md's new assertion: a schedule refreshes UA, and only the release train changes what a hiker downloads.
    A workflow a scheduled one dispatches publishes on that schedule too, so its publish steps are held the same:
    refresh-reference.yml publishes through build-reference.yml."""
    checked = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = _load(path)
        if "schedule" not in _triggers(workflow) or path.name in PRODUCTION_ON_A_SCHEDULE:
            continue
        for name in [path.name, *sorted(_dispatched(workflow))]:
            publisher = workflow if name == path.name else _load(WORKFLOWS / name)
            for job_id, job in (publisher.get("jobs") or {}).items():
                for step in _publishes(job):
                    environment = {**(publisher.get("env") or {}), **(job.get("env") or {}), **(step.get("env") or {})}
                    assert environment.get("OURHIKE_DATA_ENV") == "ua", (
                        f"{name}:{job_id}, on {path.name}'s schedule, publishes with OURHIKE_DATA_ENV "
                        f"{environment.get('OURHIKE_DATA_ENV')!r}; only the literal 'ua' may"
                    )
                    checked.append(path.name)
    assert {"refresh-reference.yml", "publish-weather.yml"} <= set(checked), checked


def test_the_one_scheduled_production_publisher_is_still_the_conditions_bake():
    for name in PRODUCTION_ON_A_SCHEDULE:
        workflow = _load(WORKFLOWS / name)
        assert "schedule" in _triggers(workflow), f"{name} lost its schedule, so its exemption here is stale"
