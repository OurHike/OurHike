"""build-reference.yml, the monthly lane's build from a pin: it builds only from a raw_run that has one, nothing in it
can reach production, and each job holds only its own keys.

The maintainer's choice B (poll, 2026-10-08) cut the build, publish, confirm
and parity jobs out of refresh-reference.yml, so that a fix to a build that
failed after a good extract can be tried on that extract's pin without paying
for another (refresh-reference.yml's header has the run 29 times). What this
file holds came over with those jobs from test_refresh_reference.py, each
assertion moved to the workflow that now holds its subject: the build through
build_marts.py's monthly lane and from the pin alone, the EPQS answers carried
between attempts, the row history, the parity groups and their public
artifact, the UA publish inside publish-data, the confirm job that sees a
cancelled publish (#1513 - A queued publish is silently cancelled when another
one joins publish-data, and it looks like a green build), and the two
workflows that count a run by that confirm job.

New with the split: the one input, `raw_run`, is held to an extract run id's
shape before anything else runs and reaches every script through env
(test_run_steps_take_inputs_through_env.py's rule for every run step); a
raw_run with no pin stops the build by name; nothing here needs
refresh-reference.yml's extract job; the two files share one concurrency group
and one list of cached paths, so the EPQS answers the pin job saves are the
ones the build restores.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from test_refresh_reference import (
    BASH,
    ELEVATION_ANSWERS,
    PIN_STEPS,
    PUBLIC_BUCKET_SECRETS,
    RAW_RUN,
    RAW_STORE_SECRETS,
    WORKFLOWS,
    _cache_steps,
    _cached_paths,
    _first_step,
    _load,
    _runs,
    _secrets,
    _strings,
    _triggers,
)

NAME = "build-reference.yml"
REFRESH = "refresh-reference.yml"
#: The parity job's families and groups, which the job runs by name from pipeline/.
LANE = Path(__file__).resolve().parents[2] / "pipeline" / "parity_lane.py"
#: The name two other workflows count a run of this one by (check-upstream-freshness.yml, build-data-release.yml).
CONFIRM = "Confirm UA serves what the build wrote"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return _load(WORKFLOWS / NAME)


@pytest.fixture(scope="module")
def refresh() -> dict:
    return _load(WORKFLOWS / REFRESH)


def test_it_runs_only_on_a_dispatch_whose_one_input_is_a_required_raw_run(workflow):
    """No schedule (the lane's clock is refresh-reference.yml's) and no input that could name an environment."""
    triggers = _triggers(workflow)

    assert set(triggers) == {"workflow_dispatch"}
    (name,) = triggers["workflow_dispatch"]["inputs"]
    spec = triggers["workflow_dispatch"]["inputs"]["raw_run"]
    assert name == "raw_run" and spec["required"] is True and spec["type"] == "string"


def test_every_run_names_its_raw_run_in_its_title(workflow):
    """check-upstream-freshness.yml dates UA's monthly data by the raw_run in a run's title (its display_title)."""
    assert workflow["run-name"] == "Build reference data from raw_run ${{ inputs.raw_run }}"


def test_nothing_in_it_names_any_environment_but_ua(workflow):
    values = _strings(workflow["jobs"])

    assert "data_environment" not in "\n".join(values)
    assert not [value for value in values if "production" in value], "no value in the file may name production"
    for job_id, job in workflow["jobs"].items():
        assert job.get("environment") in (None, "ua"), f"{job_id}'s environment is {job.get('environment')!r}"
        for step in job.get("steps") or []:
            if "OURHIKE_DATA_ENV" in (step.get("env") or {}):
                assert step["env"]["OURHIKE_DATA_ENV"] == "ua", f"{job_id}: {step.get('name')}"


def test_the_raw_run_reaches_every_script_through_env_and_is_never_pasted_into_one(workflow):
    """`${{ }}` is substituted before bash parses a script, so a raw_run pasted into one would be the script
    (test_run_steps_take_inputs_through_env.py holds the same rule for every workflow, by input type)."""
    for job_id, job in workflow["jobs"].items():
        for step in job.get("steps") or []:
            assert "inputs." not in str(step.get("run") or ""), f"{job_id}: {step.get('name')} pastes an input"
    for job_id in ("build", "parity", "parity-report"):
        assert workflow["jobs"][job_id]["env"]["RAW_RUN"] == "${{ inputs.raw_run }}", job_id


def test_nothing_in_it_needs_refresh_references_extract_job(workflow):
    """The raw_run comes from the input and everything else from the pin in R2: no job of this file names the extract
    job, whose outputs a dispatched run cannot read, nor its monthly-extract-report artifact, which no build or parity
    step ever downloaded."""
    text = (WORKFLOWS / NAME).read_text(encoding="utf-8")

    assert "needs.extract" not in text and "monthly-extract-report" not in text
    for job_id, job in workflow["jobs"].items():
        needs = job.get("needs") or []
        assert "extract" not in ([needs] if isinstance(needs, str) else needs), job_id


def test_both_halves_of_the_lane_share_one_group_and_a_queued_run_is_never_cancelled_by_a_running_one(workflow, refresh):
    """The raw store's monthly prefix and the step cache keep one writer: the build refresh-reference.yml dispatches
    queues behind the run that dispatched it."""
    assert workflow["concurrency"] == refresh["concurrency"] == {"group": "raw-lake-monthly", "cancel-in-progress": False}


def test_dlt_and_dbt_telemetry_are_off_for_every_job(workflow):
    assert workflow["env"]["RUNTIME__DLTHUB_TELEMETRY"] == "false"
    assert workflow["env"]["DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS"] == "false"
    for job_id, job in workflow["jobs"].items():
        assert "RUNTIME__DLTHUB_TELEMETRY" not in (job.get("env") or {}), f"{job_id} overrides it"


def test_only_the_publish_job_holds_the_public_buckets_keys_or_the_write_switch(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for job_id, job in workflow["jobs"].items():
        holds = _secrets(job) & PUBLIC_BUCKET_SECRETS
        writes = "R2_WRITE_ENABLED" in yaml.safe_dump(job)
        assert "permissions" not in job, f"{job_id} widens the workflow's permissions"
        if job_id == "publish":
            assert holds == PUBLIC_BUCKET_SECRETS and writes
        else:
            assert not holds and not writes, f"{job_id} holds {sorted(holds)} or R2_WRITE_ENABLED"


@pytest.mark.parametrize("job_id", ["build", "parity"])
def test_a_job_holding_the_raw_store_key_names_every_raw_secret_before_it_uses_one(workflow, job_id):
    steps = workflow["jobs"][job_id]["steps"]
    first = next(index for index, step in enumerate(steps) if _secrets(step))
    check = steps[first]

    assert "missing" in (check.get("run") or ""), f"{job_id}'s first step holding a secret is not the check"
    for name in sorted(RAW_STORE_SECRETS | {"R2_ENDPOINT_URL"}):
        assert name in check["run"] and name in (check.get("env") or {}), f"{job_id} does not check {name} by name"


# --- The one input: held to a raw_run's shape, then to a pin ---


def _shape_check(workflow: dict) -> dict:
    return workflow["jobs"]["build"]["steps"][0]


def test_the_build_s_first_step_holds_the_raw_run_to_its_shape_before_the_checkout_or_any_secret(workflow):
    steps = workflow["jobs"]["build"]["steps"]
    step = _shape_check(workflow)
    checkout = next(index for index, other in enumerate(steps) if str(other.get("uses", "")).startswith("actions/checkout"))

    assert "uses" not in step and not _secrets(step) and checkout == 1
    assert step["working-directory"] == ".", "the job's pipeline/ is not there before the checkout"
    assert "RAW_RUN" in step["run"] and "${{" not in step["run"]


def _check_shape(workflow: dict, tmp_path: Path, raw_run: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*BASH, _shape_check(workflow)["run"]],
        cwd=tmp_path,
        env={**os.environ, "RAW_RUN": raw_run},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_a_raw_run_with_an_extract_run_ids_shape_passes(workflow, tmp_path):
    """extract/_run.py stamps a run's id with "%Y%m%dT%H%M%S.%fZ" (monthly run 29's was 20261008T041936.333353Z)."""
    assert _check_shape(workflow, tmp_path, RAW_RUN).returncode == 0
    assert _check_shape(workflow, tmp_path, "20261103T051512.000001Z").returncode == 0


@pytest.mark.parametrize(
    "raw_run",
    [
        "",
        "20261008T041936Z",
        "2026-10-08T04:19:36.333353Z",
        " 20261008T041936.333353Z",
        "20261008T041936.333353Z\n",
        "../20261008T041936.333353Z",
        "20261008T041936.333353Z; touch PWNED",
        "20261008T041936.333353Z$(touch PWNED)",
        "`touch PWNED`",
        "20261008T041936.333353Z\n::warning title=Injected::a workflow command",
    ],
    ids=[
        "empty",
        "no-microseconds",
        "iso",
        "leading-space",
        "trailing-newline",
        "path",
        "semicolon",
        "substitution",
        "backticks",
        "workflow-command",
    ],
)
def test_anything_else_is_refused_by_name_and_never_run(workflow, tmp_path, raw_run):
    """An injection-shaped raw_run is refused, its text never runs, and printing it cannot start a workflow command of
    its own: the error shows it through printf %q, one line."""
    completed = _check_shape(workflow, tmp_path, raw_run)

    assert completed.returncode == 1, completed.stdout
    assert completed.stdout.startswith("::error title=Not a raw_run::raw_run ") and "nothing was built" in completed.stdout
    assert [line for line in completed.stdout.splitlines() if line.startswith("::")] == completed.stdout.splitlines()[:1]
    assert not (tmp_path / "PWNED").exists()


def _pin_check(workflow: dict) -> dict:
    (step,) = [step for step in workflow["jobs"]["build"]["steps"] if "extract._warehouse has-pin" in (step.get("run") or "")]
    return step


def _check_pin(workflow: dict, tmp_path: Path, out: str, status: int, err: str = "") -> tuple[int, str, list[str]]:
    """The pin check's script, with a stand-in for the extract venv's python that answers as has-pin would."""
    python = tmp_path / "runner" / "extract" / "bin" / "python"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        "with open(os.environ['STUB_LOG'], 'w') as log:\n    json.dump(sys.argv[1:], log)\n"
        f"print({out!r})\nprint({err!r}, file=sys.stderr)\nsys.exit({status})\n"
    )
    python.chmod(0o755)
    completed = subprocess.run(
        [*BASH, _pin_check(workflow)["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "RUNNER_TEMP": str(tmp_path / "runner"),
            "RAW_RUN": RAW_RUN,
            "R2_RAW_BUCKET": "our-hike-raw",
            "STUB_LOG": str(tmp_path / "argv.json"),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode, completed.stdout, json.loads((tmp_path / "argv.json").read_text())


def test_a_pinned_raw_run_passes_the_pin_check(workflow, tmp_path):
    status, out, argv = _check_pin(workflow, tmp_path, f"raw_run {RAW_RUN}: pinned under s3://x", 0)

    assert status == 0 and "::error" not in out
    store = "--lane monthly --bucket-url s3://our-hike-raw/raw/dlt/monthly --steps-url s3://our-hike-raw/steps"
    assert argv == ["-m", "extract._warehouse", "has-pin", *store.split(), "--raw-run", RAW_RUN]


def test_a_raw_run_with_no_pin_stops_the_build_by_name(workflow, tmp_path):
    """has-pin exits 1 and says "not pinned" for a raw_run with no raw_inputs.json (extract/_warehouse.py)."""
    status, out, _argv = _check_pin(workflow, tmp_path, f"raw_run {RAW_RUN}: not pinned under s3://x", 1)

    assert status == 1
    assert f"::error title=No pin::raw_run {RAW_RUN} has no pin; dispatch refresh-reference.yml to extract one" in out


@pytest.mark.parametrize("status", [1, 2])
def test_a_store_that_cannot_be_read_is_never_reported_as_a_missing_pin(workflow, tmp_path, status):
    """A crash exits 1 too (Python's own exit for an uncaught exception), with its traceback on stderr and no "not
    pinned" on stdout; it fails the step under its own name."""
    code, out, _argv = _check_pin(workflow, tmp_path, "", status, err="botocore.exceptions.ClientError: 403")

    assert code == 1 and "has no pin" not in out and "::error title=The pin could not be read::" in out


def test_the_pin_check_runs_before_dbts_packages_and_the_build(workflow):
    steps = workflow["jobs"]["build"]["steps"]
    check = steps.index(_pin_check(workflow))
    install = next(
        index for index, step in enumerate(steps) if step.get("name") == "Install dbt, the extract's pins and the pipeline's pins"
    )

    assert install < check < _first_step(steps, "generate_dbt.py") < _first_step(steps, "extract._warehouse load")
    assert RAW_STORE_SECRETS <= _secrets(_pin_check(workflow))


# --- The build: from the pin alone, through build_marts.py ---


def test_the_build_holds_the_steps_from_the_warehouse_on_and_none_of_the_pins(workflow):
    """Choice B moved these whole from refresh-reference.yml's build job; the steps down to the pin are its pin job's
    (test_refresh_reference.py)."""
    names = [step.get("name") for step in workflow["jobs"]["build"]["steps"]]
    runs = _runs(workflow["jobs"]["build"])
    moved = [
        "Build the warehouse from the pin",
        "dbt build, the Python steps and the pub_ writers (build_marts.py --lane monthly)",
        # Not moved: decision 31's new-data counts, added after the split (test_the_new_data_review_*).
        "The new-data review's counts, from the built warehouse (new_data_report.py --facts-out)",
        "Hand the new-data counts on",
        "Save the EPQS answers and the DEM samples",
        "Save dbt's DuckDB driver and v2's spatial extension",
        "Store the warehouse and its manifest in the step cache",
        "Hand the phone files on",
    ]

    assert names[-len(moved) :] == moved
    assert not set(PIN_STEPS) & set(names)
    for command in ("extract._warehouse pin ", "extract._warehouse as-landed", "extract._geofabrik", "fetch_osm_water.py"):
        assert command not in runs, command


def test_the_build_runs_through_build_marts_monthly_lane_and_no_dbt_command_of_its_own(workflow):
    runs = _runs(workflow["jobs"]["build"])

    assert "python build_marts.py --lane monthly" in runs
    assert not re.search(r"\bdbt (build|run|seed|test)\b", runs), "the build order is build_marts.py's alone"


def test_the_build_builds_from_the_pin_and_writes_only_under_steps(workflow):
    runs = _runs(workflow["jobs"]["build"])
    steps = workflow["jobs"]["build"]["steps"]

    assert "extract._run" not in runs, "the build job never extracts, so it never writes the raw store's raw/"
    assert re.search(r"extract\._warehouse load .*--raw-run", runs.replace("\n", " ")), "the warehouse comes from the pin"
    for match in re.finditer(r'--steps-url "([^"]+)"', runs):
        assert match.group(1) == "s3://$R2_RAW_BUCKET/steps", match.group(0)
    assert "extract._warehouse store" in runs
    assert _first_step(steps, "extract._warehouse load") < _first_step(steps, "build_marts.py --lane monthly")


def test_the_build_restores_and_saves_the_epqs_answers_and_the_dem_samples_around_build_marts(workflow):
    """ARC-3 of PR #1805's second review: monthly runs 20, 21 and 22 each asked USGS EPQS about the same 3,118 corridor
    OSM water points again, for 21.3, 41.5 and 54.2 min, because nothing carried an answer from one attempt to the next.
    publish-vector-data.yml carries both files in FETCH_OUTPUTS. Restored before build_marts.py and on every run, since
    every run here builds from an existing pin and still grades and samples; saved after build_marts.py, and on a failed
    run too."""
    job = workflow["jobs"]["build"]
    steps = job["steps"]
    (restore,) = _cache_steps(job, workflow, "restore")
    (save,) = _cache_steps(job, workflow, "save")

    assert restore < _first_step(steps, "build_marts.py") and "if" not in steps[restore]
    assert save > _first_step(steps, "build_marts.py --lane monthly")
    assert "always()" in str(steps[save]["if"])
    prefix = str(steps[save]["with"]["key"]).split("${{")[0]
    assert prefix and str(steps[restore]["with"]["restore-keys"]).strip() == prefix


def test_the_epqs_answers_cross_from_the_pin_job_to_the_build_under_one_prefix_and_one_path_list(workflow, refresh):
    """An actions/cache entry is found only by the paths it was saved with (its version stamps them), on the branch it
    was saved on or the default branch (GitHub's docs, "Dependency caching reference"). So the two files declare one
    list, word for word, the pin job saves under the prefix the build restores, and the dispatch names the pin job's
    own ref. @unvalidated in a run: this holds the files, not GitHub."""
    assert workflow["env"]["ELEVATION_ANSWERS"] == refresh["env"]["ELEVATION_ANSWERS"]
    assert _cached_paths({"with": {"path": workflow["env"]["ELEVATION_ANSWERS"]}}, {}) == ELEVATION_ANSWERS
    pin = refresh["jobs"]["pin"]
    (saved,) = _cache_steps(pin, refresh, "save")
    (restored,) = _cache_steps(workflow["jobs"]["build"], workflow, "restore")
    prefix = str(pin["steps"][saved]["with"]["key"]).split("${{")[0]
    assert str(workflow["jobs"]["build"]["steps"][restored]["with"]["restore-keys"]).strip() == prefix
    (dispatch,) = [step for step in refresh["jobs"]["dispatch"]["steps"] if "gh workflow run" in (step.get("run") or "")]
    assert dispatch["env"]["REF"] == "${{ github.ref_name }}" and '--ref "$REF"' in dispatch["run"]


def test_every_parity_group_reads_the_builds_epqs_answers_and_never_saves_them(workflow):
    """Today's OSM water grade asks EPQS one point at a time through fetch_trail_water.elevation_ft()'s disk cache,
    which is this cache's first file: one at a time, monthly run 23's grade asked from 06:09 to 09:05 UTC and was
    cancelled. Restored from the build job's entry, so the old side asks only for the walks the dbt side never did."""
    build, job = workflow["jobs"]["build"], workflow["jobs"]["parity"]
    steps = job["steps"]
    (restore,) = _cache_steps(job, workflow, "restore")
    (saved,) = _cache_steps(build, workflow, "save")

    assert "if" not in steps[restore], "every group, so a POI family moved between groups is never graded cold"
    assert restore < _first_step(steps, "parity_lane.py --group") and restore > _first_step(steps, "extract._warehouse load")
    assert str(steps[restore]["with"]["restore-keys"]).strip() == str(build["steps"][saved]["with"]["key"]).split("${{")[0]
    assert not [step for step in steps if str(step.get("uses", "")).startswith("actions/cache/save")]


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


# --- Publish and confirm ---


def test_the_publish_job_stages_the_dbt_writers_files_on_ua_inside_publish_data(workflow):
    job = workflow["jobs"]["publish"]
    step = next(step for step in job["steps"] if step.get("run") == "python publish.py")

    assert step["env"]["OURHIKE_PHONE_FILES"] == "dbt" and step["env"]["OURHIKE_DATA_ENV"] == "ua"
    assert job["concurrency"] == {"group": "publish-data", "cancel-in-progress": False}
    assert job["needs"] == "build"


def test_confirm_runs_when_publish_was_cancelled_and_holds_no_credential(workflow):
    job = workflow["jobs"]["confirm"]

    assert job["name"] == CONFIRM, "check-upstream-freshness.yml and build-data-release.yml count a run by this name"
    assert "always()" in job["if"] and "needs.build.result == 'success'" in job["if"]
    assert set(job["needs"]) == {"build", "publish"}
    assert not _secrets(job)


def test_the_freshness_check_dates_the_monthly_refresh_by_this_files_confirm_job_and_its_raw_run():
    """check-upstream-freshness.yml's 35-day alarm reads this workflow's runs on main; how it counts and dates them
    is test_monthly_refresh_counts_a_run_that_refreshed_ua.py's, against a stand-in API."""
    workflow = _load(WORKFLOWS / "check-upstream-freshness.yml")
    job = workflow["jobs"]["check"]
    step = next(step for step in job["steps"] if step.get("id") == "monthly")

    assert step["env"]["MONTHLY_WORKFLOW"] == NAME and step["env"]["MAX_AGE_DAYS"] == "35"
    assert CONFIRM in step["run"] and "display_title" in step["run"]
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
    # Which runs count is test_monthly_refresh_counts_a_run_that_refreshed_ua.py's, against a stand-in API.
    assert '"schedule"' in script and f"{NAME}/runs?branch=main&status=completed" in script and CONFIRM in script
    assert "workflow_dispatch" in _triggers(workflow), "the dispatch stays (decision 28a)"
    assert not _secrets(give_way) and not _secrets(workflow["jobs"]["plan"])


# --- Parity ---


def _lane_literal(name: str):
    """parity_lane.py's module-level literal `name`, read without importing the file: it is a pipeline script."""
    for node in ast.parse(LANE.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"parity_lane.py has no literal {name}")


def test_the_parity_job_writes_nothing_and_runs_one_group_of_families_per_runner(workflow):
    job = workflow["jobs"]["parity"]
    runs = _runs(job)

    assert job["needs"] == "build"
    assert not re.search(r"extract\._warehouse (pin|store)\b", runs)
    assert 'parity_lane.py --group "$GROUP" --out "$PARITY_DIR"' in runs
    assert job["strategy"]["fail-fast"] is False, "one group's failure must not cancel the others' answers"
    assert job["strategy"]["matrix"]["group"] == list(_lane_literal("GROUPS")), (
        "a group the job never runs, or one the lane lacks"
    )
    uploads = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact")]
    assert uploads and uploads[-1]["if"] == "always()"
    assert uploads[-1]["with"]["name"] == "monthly-parity-${{ matrix.group }}"


def test_the_parity_report_joins_every_group_into_the_one_artifact_the_gate_reads_and_holds_no_credential(workflow):
    job = workflow["jobs"]["parity-report"]
    runs = _runs(job)

    assert not _secrets(job)
    assert set(job["needs"]) == {"build", "parity"}
    assert "always()" in job["if"] and "needs.build.result == 'success'" in job["if"]
    downloads = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/download-artifact")]
    merged = next(step for step in downloads if step["with"].get("pattern"))
    assert merged["with"] == {"pattern": "monthly-parity-*", "path": "${{ runner.temp }}/parity", "merge-multiple": True}
    assert 'parity_lane.py --join "$PARITY_DIR" --raw-run "$RAW_RUN"' in runs
    assert 'gate_report.py --parity-dir "$PARITY_DIR/results"' in runs
    uploads = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact")]
    assert uploads[-1]["if"] == "always()" and uploads[-1]["with"]["name"] == "monthly-parity"


def _step(job: dict, name: str) -> tuple[int, dict]:
    steps = job["steps"]
    found = [index for index, step in enumerate(steps) if step.get("name") == name]
    assert found, f"no step named {name!r}"
    return found[0], steps[found[0]]


def test_the_new_data_review_counts_the_warehouse_this_build_wrote_and_never_holds_up_the_ua_publish(workflow):
    """Decision 31's report needs the warehouse, which only the build job holds, and every parity group's results,
    which only parity-report holds: the build counts its own warehouse right after build_marts.py writes it, so the
    counts describe the files this run's parity compares, and hands on the counts, never the warehouse."""
    job = workflow["jobs"]["build"]
    names = [step.get("name") for step in job["steps"]]
    at, facts = _step(job, "The new-data review's counts, from the built warehouse (new_data_report.py --facts-out)")
    hand, upload = _step(job, "Hand the new-data counts on")

    assert names.index("dbt build, the Python steps and the pub_ writers (build_marts.py --lane monthly)") < at < hand
    assert at < names.index("Store the warehouse and its manifest in the step cache")
    run = " ".join(facts["run"].split())
    assert "new_data_report.py --warehouse data/warehouse.duckdb --facts-out" in run
    assert facts.get("continue-on-error") is True, "a review the build could not count must not keep UA's data back"
    assert not _secrets({"steps": [facts]}), "it reads a local file"
    assert upload["if"] == f"steps.{facts['id']}.outcome == 'success'"
    assert upload["with"]["name"] == "monthly-new-data-facts"
    assert upload["with"]["path"].endswith("/new_data/new_data_facts.json")


def test_the_new_data_review_report_is_written_beside_every_parity_groups_results_and_kept_with_its_counts_shown(workflow):
    job = workflow["jobs"]["parity-report"]
    download_at, download = _step(job, "The build's new-data counts")
    report_at, report = _step(job, "The new-data review report (new_data_report.py)")
    keep_at, keep = _step(job, "Keep the new-data review report")
    gate_at, gate = _step(job, "The gate's per-key report")

    assert download["with"] == {"name": "monthly-new-data-facts", "path": "${{ runner.temp }}/new_data"}
    assert download.get("continue-on-error") is True, "a build that could not count leaves a warning, not a red report"
    run = " ".join(report["run"].split())
    assert 'new_data_report.py --facts "$facts" "${parity[@]}"' in run and '--summary "$GITHUB_STEP_SUMMARY"' in run
    assert 'parity=(--parity-dir "$PARITY_DIR/results")' in run
    assert gate_at < download_at < report_at < keep_at
    assert keep["if"] == "always()" and keep["with"]["name"] == "monthly-new-data-report"
    assert keep["with"]["path"] == "${{ runner.temp }}/new_data/report/"
    assert '--summary "$GITHUB_STEP_SUMMARY"' in " ".join(gate["run"].split()), "the gate's counts go on the page too"


def test_the_new_data_report_step_warns_and_writes_nothing_when_the_build_could_not_count(workflow, tmp_path):
    """Run as the job runs it, with no facts file: a warning naming why, an exit 0, and no report invented."""
    _, report = _step(workflow["jobs"]["parity-report"], "The new-data review report (new_data_report.py)")
    summary = tmp_path / "summary.md"
    env = {
        **os.environ,
        "PARITY_DIR": str(tmp_path / "parity"),
        "NEW_DATA_DIR": str(tmp_path / "new_data"),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(summary),
    }

    done = subprocess.run([*BASH, report["run"]], env=env, capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    assert "::warning title=No new-data counts::" in done.stdout
    assert not (tmp_path / "new_data" / "report").exists() and not summary.exists()


STUB_PARITY = """
import json, os, pathlib
def main(argv):
    with open(os.environ["STUB_LOG"], "a") as log:
        log.write(json.dumps(argv) + "\\n")
    print(f"{argv[0]}: no differences across 0 records, keyed by id")
    results = pathlib.Path(argv[argv.index("--json-dir") + 1])
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{argv[0]}.json").write_text(json.dumps({"outcome": "no_differences"}))
    return 0
"""


def test_every_monthly_parity_run_writes_keys_only_into_the_uploaded_folder(workflow, tmp_path):
    """The monthly-parity artifact is public, and its old side holds held-back sources: parity.py's
    --keys-only (tests/test_parity.py) is what keeps their records and geometry out of it. Each group's command line
    runs here as the job runs it, with a stand-in parity.py beside parity_lane.py, and the join as parity-report runs it."""
    job = workflow["jobs"]["parity"]
    step = next(step for step in job["steps"] if step.get("name") == "Parity with today's exporters")
    upload = next(step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact"))
    report = workflow["jobs"]["parity-report"]
    joined = next(step for step in report["steps"] if step.get("name") == "Every group's answers in one summary")
    assert step["env"]["PARITY_DIR"] == joined["env"]["PARITY_DIR"] == "${{ runner.temp }}/parity"
    assert upload["with"]["path"].rstrip("/") == "${{ runner.temp }}/parity"

    work = tmp_path / "work"
    work.mkdir()
    shutil.copyfile(LANE, work / "parity_lane.py")
    (work / "parity.py").write_text(STUB_PARITY)
    python = tmp_path / "runner" / "pipeline" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    python.chmod(0o755)
    # Every group into one folder, as parity-report's merge-multiple download leaves them.
    parity_dir = tmp_path / "runner" / "parity"
    env = {
        **os.environ,
        "PARITY_DIR": str(parity_dir),
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "RAW_RUN": "1",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "STUB_LOG": str(tmp_path / "calls.jsonl"),
    }
    for group in job["strategy"]["matrix"]["group"]:
        subprocess.run(["bash", "-c", step["run"]], cwd=work, env={**env, "GROUP": group}, check=True, capture_output=True)
    subprocess.run(["bash", "-c", joined["run"]], cwd=work, env=env, check=True, capture_output=True)

    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert sorted(argv[0] for argv in calls) == sorted(_lane_families()), "every family once, and nothing else"
    for argv in calls:
        assert "--keys-only" in argv, argv
        assert argv[argv.index("--json-dir") + 1] == str(parity_dir / "results"), argv
    summary = json.loads((parity_dir / "summary.json").read_text())
    assert summary["raw_run"] == "1"
    assert {entry["status"] for entry in summary["families"].values()} == {"match"}, "the status comes from results/<family>.json"
    assert (tmp_path / "summary.md").read_text().count(" | match |") == len(_lane_families())


# --- The parity families, one home: CI's own step ---

# `--json-dir <dir>` (gate_report.py's results, on every CI line) may sit between parity.py and the family,
# and a family's name may hold a digit (stage 6's `elevation_v2`).
CI_PARITY = re.compile(
    r'parity\.py (?:--json-dir \S+ )?"?([a-z0-9_$]+)"? --new "?data/processed/dbt/([^ "]+?)"?(?= |$)( --raw-dir data/raw)?',
    re.M,
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


def _lane_families() -> dict[str, tuple[str, bool]]:
    """parity_lane.py's FAMILIES: each family's file and whether it is handed --raw-dir data/raw."""
    return {family: (name, reads_raw) for family, (name, reads_raw) in _lane_literal("FAMILIES").items()}


def test_the_monthly_parity_runs_every_family_ci_runs_except_the_hourly_conditions_files():
    ci = _ci_families()

    assert HOURLY_FAMILIES <= set(ci), "a conditions family left CI's step; HOURLY_FAMILIES is stale"
    assert _lane_families() == {family: entry for family, entry in ci.items() if family not in HOURLY_FAMILIES}
