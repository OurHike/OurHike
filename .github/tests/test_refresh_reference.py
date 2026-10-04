"""refresh-reference.yml, the monthly lane: nothing in it can reach production, and each job holds only its own keys.

pipeline/ELT.md, "Why a scheduled run cannot reach production", lists the
locks: no input names an environment, the one publish writes UA's keys by a
literal, and promotion is the release train's. This file holds the ones a
workflow file can hold, and the rest ELT.md asks of the lane: its schedule,
its one-run-at-a-time group, dlt's telemetry off, the build through
build_marts.py's monthly lane, the confirm job that sees a cancelled
publish (#1513 - A queued publish is silently cancelled when another one
joins publish-data, and it looks like a green build), and the two other
workflows the lane changes.

It also holds ELT.md's new assertion for every scheduled workflow that
publishes ("Repository tests a new workflow must satisfy"): each names UA as
a literal, and publish-conditions.yml's production leg is the one exemption.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
NAME = "refresh-reference.yml"
PUBLIC_BUCKET_SECRETS = {"R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}
RAW_STORE_SECRETS = {"R2_RAW_BUCKET", "R2_RAW_ACCESS_KEY_ID", "R2_RAW_SECRET_ACCESS_KEY"}
SECRET = re.compile(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)")
# The scheduled publishers that write production, each with why: publish-conditions.yml
# bakes conditions/ for both environments hourly, outside every release folder, because
# "a closure that has reopened must stop being served" (pipeline/DATA_RELEASES.md:274;
# ELT.md, "The conditions bake keeps publishing straight to production").
PRODUCTION_ON_A_SCHEDULE = {"publish-conditions.yml"}


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


def test_only_the_publish_job_holds_the_public_buckets_keys_or_the_write_switch(workflow):
    for job_id, job in workflow["jobs"].items():
        holds = _secrets(job) & PUBLIC_BUCKET_SECRETS
        writes = "R2_WRITE_ENABLED" in yaml.safe_dump(job)
        if job_id == "publish":
            assert holds == PUBLIC_BUCKET_SECRETS and writes
        else:
            assert not holds and not writes, f"{job_id} holds {sorted(holds)} or R2_WRITE_ENABLED"


def test_the_extract_job_holds_the_raw_store_and_the_upstream_credentials_and_nothing_else(workflow):
    # The two upstream credentials: Hike Finder's password, and the NPS Data API's key for decision 54's NPS places
    # and campgrounds (extract/_ogc.py's JsonFeatures), both optional and both warned about when unset.
    upstream = {"HIKEFINDER_PASSWORD", "NPS_API_KEY"}
    assert _secrets(workflow["jobs"]["extract"]) == RAW_STORE_SECRETS | {"R2_ENDPOINT_URL"} | upstream


@pytest.mark.parametrize("job_id", ["extract", "build", "parity"])
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


def test_a_layer_refused_on_its_own_lets_the_build_run_and_the_last_job_go_red(workflow):
    """Monthly runs 10, 11, 12, 14 and 15 each stopped on one layer; extract/_run.py's ISOLATING_LANES now exits 3."""
    extract = workflow["jobs"]["extract"]
    (step,) = [step for step in extract["steps"] if step.get("id") == "extract"]
    assert '"$status" -eq 3' in step["run"] and "partial=true" in step["run"]
    assert '--summary "$GITHUB_STEP_SUMMARY"' in step["run"], "the summary names each refused layer"
    assert extract["outputs"]["partial"] == "${{ steps.extract.outputs.partial }}"

    refused = workflow["jobs"]["refused"]
    assert refused["if"] == "always() && needs.extract.outputs.partial == 'true'"
    assert set(refused["needs"]) == set(workflow["jobs"]) - {"refused"}, "after every other job"
    assert not _secrets(refused) and "exit 1" in _runs(refused)


def test_the_build_runs_through_build_marts_monthly_lane_and_no_dbt_command_of_its_own(workflow):
    runs = _runs(workflow["jobs"]["build"])

    assert "python build_marts.py --lane monthly" in runs
    assert not re.search(r"\bdbt (build|run|seed|test)\b", runs), "the build order is build_marts.py's alone"


def test_the_build_builds_from_the_pin_and_writes_only_under_steps(workflow):
    runs = _runs(workflow["jobs"]["build"])

    assert "extract._run" not in runs, "the build job never extracts, so it never writes the raw store's raw/"
    assert re.search(r"extract\._warehouse load .*--raw-run", runs.replace("\n", " ")), "the warehouse comes from the pin"
    for match in re.finditer(r'--steps-url "([^"]+)"', runs):
        assert match.group(1) == "s3://$R2_RAW_BUCKET/steps", match.group(0)
    for command in ("pin", "store"):
        assert f"extract._warehouse {command}" in runs


def _first_step(steps: list[dict], text: str) -> int:
    found = [index for index, step in enumerate(steps) if text in (step.get("run") or "")]
    assert found, f"no build step runs {text!r}"
    return found[0]


def test_the_build_scans_osm_water_from_the_raw_stores_extracts_before_the_pin_that_build_marts_reads(workflow):
    """#1652 - Download OSM's Geofabrik extracts at most once a month, into a private raw bucket that outlives the
    7-day Actions cache. The copies come down after today's fetchers' files (fetch_trail_water.py --derive reads ATC's
    sites from the as-landed copy), both scans run over them before the pin, the pin carries the scans, and
    build_marts.py lands them from the pin through the warehouse step's materialised files."""
    steps = workflow["jobs"]["build"]["steps"]
    as_landed = _first_step(steps, "extract._warehouse as-landed")
    pull = _first_step(steps, "-m extract._geofabrik pull")
    osm = _first_step(steps, "fetch_osm_water.py")
    site = _first_step(steps, "fetch_trail_water.py --derive")
    landed = _first_step(steps, "-m extract._geofabrik landed")
    pin = _first_step(steps, "extract._warehouse pin ")
    load = _first_step(steps, "extract._warehouse load")
    marts = _first_step(steps, "build_marts.py --lane monthly")

    assert as_landed < pull < osm == site < landed < pin < load < marts
    # extract/_geofabrik.py's SCANS: each scan pinned under derived/, never at its scanner's own path.
    for pinned, local in {
        "derived/osm_water.geojson": "osm_water.geojson",
        "derived/trail_water.json": "trail_water.json",
    }.items():
        assert f"--extra {pinned}=data/raw/{local}" in steps[pin]["run"], pinned


def test_the_water_scans_run_only_on_a_complete_set_never_fail_the_build_and_free_the_disk(workflow):
    """A missing or unreadable copy lands the last landed scans rather than a scan of part of the corridor, and a scan
    that refuses or crashes leaves them standing: neither may stop the rest of the monthly build."""
    steps = workflow["jobs"]["build"]["steps"]
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
    steps = workflow["jobs"]["build"]["steps"]
    check = next(index for index, step in enumerate(steps) if step.get("id") == "pinned")
    pin = _first_step(steps, "extract._warehouse pin ")

    assert "extract._warehouse has-pin" in steps[check]["run"]
    for step in steps[check + 1 : pin + 1]:
        assert "steps.pinned.outputs.pinned" in step.get("if", ""), step.get("name")


def test_the_build_keeps_the_row_history_at_history_monthly_through_the_extracts_venv(workflow):
    """pipeline/row_history.py: the snapshots go in the raw store's bucket under this lane's own prefix, and the
    restore and save need s3fs, which only the extract's venv carries."""
    (step,) = [step for step in workflow["jobs"]["build"]["steps"] if "build_marts.py" in (step.get("run") or "")]

    assert '--history-url "s3://$R2_RAW_BUCKET/history/monthly"' in step["run"]
    assert '--history-python "$RUNNER_TEMP/extract/bin/python"' in step["run"]
    assert "--history-cold-start" not in step["run"], "a cold start is row_history_stores.toml's to allow, never a flag"
    assert {"R2_RAW_BUCKET", "R2_RAW_ACCESS_KEY_ID", "R2_RAW_SECRET_ACCESS_KEY", "R2_ENDPOINT_URL"} <= _secrets(step)
    # The monthly lane fails loudly: only the conditions legs publish without their history (the maintainer, by
    # poll, 2026-10-03), so a failed restore here stops the build before dbt runs.
    assert "--history-on-failure" not in step["run"]


def test_the_parity_job_writes_nothing_and_keeps_its_answers(workflow):
    job = workflow["jobs"]["parity"]
    runs = _runs(job)

    assert not re.search(r"extract\._warehouse (pin|store)\b", runs)
    assert "parity.py" in runs and 'gate_report.py --parity-dir "$PARITY_DIR/results"' in runs
    uploads = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact")]
    assert uploads and uploads[-1]["if"] == "always()"


STUB_PARITY = """
import json, os, pathlib, sys
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
print(f"{sys.argv[1]}: no differences across 0 records, keyed by id")
results = pathlib.Path(sys.argv[sys.argv.index("--json-dir") + 1])
results.mkdir(parents=True, exist_ok=True)
(results / f"{sys.argv[1]}.json").write_text(json.dumps({"outcome": "no_differences"}))
"""


def test_every_monthly_parity_run_writes_keys_only_into_the_uploaded_folder(workflow, tmp_path):
    """The monthly-parity artifact is public, and its old side holds held-back sources: parity.py's
    --keys-only (tests/test_parity.py) is what keeps their records and geometry out of it."""
    steps = workflow["jobs"]["parity"]["steps"]
    step = next(step for step in steps if step.get("name") == "Parity with today's exporters")
    upload = next(step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact"))
    assert step["env"]["PARITY_DIR"] == "${{ runner.temp }}/parity"
    assert upload["with"]["path"].rstrip("/") == "${{ runner.temp }}/parity"

    script = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "parity.py").write_text(STUB_PARITY)
    python = tmp_path / "runner" / "pipeline" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    python.chmod(0o755)
    parity_dir = tmp_path / "runner" / "parity"
    parity_dir.mkdir()
    env = {
        **os.environ,
        "PARITY_DIR": str(parity_dir),
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "RAW_RUN": "1",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "STUB_LOG": str(tmp_path / "calls.jsonl"),
    }
    subprocess.run([sys.executable, "-c", script], cwd=tmp_path / "work", env=env, check=True, capture_output=True)

    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert len(calls) == len(_lane_families(workflow))
    for argv in calls:
        assert "--keys-only" in argv, argv
        assert argv[argv.index("--json-dir") + 1] == str(parity_dir / "results"), argv
    summary = json.loads((parity_dir / "summary.json").read_text())["families"]
    assert {entry["status"] for entry in summary.values()} == {"match"}, "the status comes from results/<family>.json"


def test_the_publish_job_stages_the_dbt_writers_files_on_ua_inside_publish_data(workflow):
    job = workflow["jobs"]["publish"]
    step = next(step for step in job["steps"] if step.get("run") == "python publish.py")

    assert step["env"]["OURHIKE_PHONE_FILES"] == "dbt" and step["env"]["OURHIKE_DATA_ENV"] == "ua"
    assert job["concurrency"] == {"group": "publish-data", "cancel-in-progress": False}
    assert job["needs"] == "build"


def test_confirm_runs_when_publish_was_cancelled_and_holds_no_credential(workflow):
    job = workflow["jobs"]["confirm"]

    assert "always()" in job["if"] and "needs.build.result == 'success'" in job["if"]
    assert set(job["needs"]) == {"build", "publish"}
    assert not _secrets(job)


def _publishes(job: dict) -> list[dict]:
    return [step for step in job.get("steps") or [] if "python publish.py" in (str(step.get("run") or "")).splitlines()]


def test_every_scheduled_workflow_that_publishes_names_ua_as_a_literal():
    """ELT.md's new assertion: a schedule refreshes UA, and only the release train changes what a hiker downloads."""
    checked = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = _load(path)
        if "schedule" not in _triggers(workflow) or path.name in PRODUCTION_ON_A_SCHEDULE:
            continue
        for job_id, job in (workflow.get("jobs") or {}).items():
            for step in _publishes(job):
                environment = {**(workflow.get("env") or {}), **(job.get("env") or {}), **(step.get("env") or {})}
                assert environment.get("OURHIKE_DATA_ENV") == "ua", (
                    f"{path.name}:{job_id} publishes on a schedule with OURHIKE_DATA_ENV "
                    f"{environment.get('OURHIKE_DATA_ENV')!r}; only the literal 'ua' may"
                )
                checked.append(path.name)
    assert {"refresh-reference.yml", "publish-weather.yml"} <= set(checked), checked


def test_the_one_scheduled_production_publisher_is_still_the_conditions_bake():
    for name in PRODUCTION_ON_A_SCHEDULE:
        workflow = _load(WORKFLOWS / name)
        assert "schedule" in _triggers(workflow), f"{name} lost its schedule, so its exemption here is stale"


def test_the_freshness_check_reports_when_the_monthly_refresh_is_over_35_days_old():
    workflow = _load(WORKFLOWS / "check-upstream-freshness.yml")
    job = workflow["jobs"]["check"]
    step = next(step for step in job["steps"] if step.get("id") == "monthly")

    assert step["env"]["MONTHLY_WORKFLOW"] == NAME and step["env"]["MAX_AGE_DAYS"] == "35"
    assert workflow["permissions"] == {"contents": "read", "issues": "write", "actions": "read"}
    issue = next(step for step in job["steps"] if step.get("name") == "Open, update, or close the tracking issue")
    assert "steps.monthly.outputs.alarm == 'true'" in issue["if"]
    assert "!refreshAlarm" in issue["with"]["script"], "an overdue refresh must keep #478 open"


def test_the_weekly_planner_gives_way_on_its_schedule_only_once_the_monthly_lane_has_run():
    workflow = _load(WORKFLOWS / "build-data-release.yml")
    give_way = workflow["jobs"]["give-way"]
    script = _runs(give_way)

    assert workflow["jobs"]["plan"]["needs"] == "give-way"
    assert workflow["jobs"]["plan"]["if"] == "needs.give-way.outputs.plan == 'true'"
    assert '"schedule"' in script and "refresh-reference.yml/runs?status=success" in script
    assert "workflow_dispatch" in _triggers(workflow), "the dispatch stays (decision 28a)"
    assert not _secrets(give_way) and not _secrets(workflow["jobs"]["plan"])


# --- The parity families, one home: CI's own step ---

# `--json-dir <dir>` (gate_report.py's results, on every CI line) may sit between parity.py and the family,
# and a family's name may hold a digit (stage 6's `elevation_v2`).
CI_PARITY = re.compile(
    r'parity\.py (?:--json-dir \S+ )?"?([a-z0-9_$]+)"? --new "?data/processed/dbt/([^ "]+?)"?(?= |$)( --raw-dir data/raw)?', re.M
)
POI_LOOP = re.compile(r"for poi_type in ([a-z ]+); do")
#: pipeline-tests.yml's parity lines for files the hourly conditions lane writes, not this one.
HOURLY_FAMILIES = {"atc_updates", "nynjtc_alerts", "closures", "reports", "weather_alerts", "work_projects"}


def _ci_families() -> dict[str, tuple[str, bool]]:
    steps = _load(WORKFLOWS / "pipeline-tests.yml")["jobs"]["dbt"]["steps"]
    script = next(step["run"] for step in steps if step.get("name") == "Parity with today's exporters")
    kinds = POI_LOOP.search(script).group(1).split()
    found = {}
    for family, name, raw in CI_PARITY.findall(script):
        for kind in kinds if "$poi_type" in family else [None]:
            found[family.replace("$poi_type", kind or "")] = (name.replace("$poi_type", kind or ""), bool(raw))
    return found


def _lane_families(workflow: dict) -> dict[str, tuple[str, bool]]:
    script = next(
        step["run"] for step in workflow["jobs"]["parity"]["steps"] if step.get("name") == "Parity with today's exporters"
    )
    block = script[script.index("families = {") + len("families = ") : script.index("statuses = ")]
    raw = ("--raw-dir", "data/raw")
    families = eval(block, {"raw": raw})  # noqa: S307 - the workflow's own literal, read to compare it with CI's
    return {family: (name, extra == raw) for family, (name, extra) in families.items()}


def test_the_monthly_parity_runs_every_family_ci_runs_except_the_hourly_conditions_files(workflow):
    ci = _ci_families()

    assert HOURLY_FAMILIES <= set(ci), "a conditions family left CI's step; HOURLY_FAMILIES is stale"
    assert _lane_families(workflow) == {family: entry for family, entry in ci.items() if family not in HOURLY_FAMILIES}
