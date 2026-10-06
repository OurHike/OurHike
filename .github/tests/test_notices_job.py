"""Decision 61's split, as the two workflows carry it: extract-notices.yml every 4 hours, publish-conditions.yml hourly.

The maintainer, 2026-10-04: every club's and agency's notices move to a job
every 4 hours with up to an hour to read, and NWS, OurHike's own moderated
closures and reports, ATC and NYNJTC stay in the short hourly job. Which
resources each job reads is extract/_run.py's job_of(), held by
pipeline/tests/test_extract_layout.py; this file holds the workflows around
it: the notices job's clock, budget, concurrency and outputs, and the hourly
job reading the notices legs' served copy without ever stopping its own
publish for it. The steps' own scripts run here under bash, with a stand-in
for the extract's python and for build_marts.py that write down what they
were asked and answer with a chosen exit.
"""

from __future__ import annotations

import ast
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
NOTICES = WORKFLOWS / "extract-notices.yml"
CONDITIONS = WORKFLOWS / "publish-conditions.yml"
EXTRACT_STEP = "Extract every club's and agency's notices into this leg's store"
SERVE_STEP = "Copy what the hourly build reads of this leg"
ADD_STEP = "Add the notices legs' newest served copy to the warehouse (dbt path)"
BUILD_STEP = "Build the closures and warnings marts and their writers (dbt path)"


def _notices_check_seconds() -> int:
    """extract/_run.py's LEG_CHECK_SECONDS for the notices job, read from its source: this suite installs no dlt."""
    tree = ast.parse((WORKFLOWS.parents[1] / "pipeline" / "extract" / "_run.py").read_text(encoding="utf-8"))
    (value,) = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "LEG_CHECK_SECONDS" for target in node.targets)
    ]
    return next(
        ast.literal_eval(seconds) for key, seconds in zip(value.keys, value.values, strict=True) if key.id == "NOTICES_JOB"
    )


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps(path: Path, job: str) -> list[dict]:
    return _load(path)["jobs"][job]["steps"]


def _step(path: Path, job: str, name: str) -> dict:
    return next(step for step in _steps(path, job) if step.get("name") == name)


def _stand_in(program: Path, status: int) -> Path:
    """An executable at `program` that writes its arguments to `<program>.args` and exits `status`. Returns that file."""
    program.parent.mkdir(parents=True, exist_ok=True)
    record = program.with_name(f"{program.name}.args")
    program.write_text(f'#!/bin/bash\necho "$@" > "{record}"\nexit {status}\n')
    program.chmod(program.stat().st_mode | stat.S_IXUSR)
    return record


def _run(script: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-e", "-c", script], env=env, capture_output=True, text=True)


def _outputs(tmp_path: Path) -> dict[str, str]:
    path = tmp_path / "output"
    return dict(line.split("=", 1) for line in path.read_text().splitlines()) if path.exists() else {}


def _base_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": f"{tmp_path / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_ENV": str(tmp_path / "env"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "R2_RAW_BUCKET": "raw-bucket",
    }


# --- extract-notices.yml ----------------------------------------------------


def test_the_notices_job_runs_every_4_hours_at_a_minute_off_the_hour():
    (schedule,) = _load(NOTICES).get("on", _load(NOTICES).get(True))["schedule"]
    minute, hour, *rest = schedule["cron"].split()
    assert rest == ["*", "*", "*"]
    assert minute.isdigit() and int(minute) != 0, "GitHub queues everything submitted at :00 behind everyone else's"
    hours = range(int(hour.split("-")[0]), int(hour.split("-")[1].split("/")[0]) + 1, int(hour.split("/")[1]))
    assert len(hours) == 6 and all(b - a == 4 for a, b in zip(hours, hours[1:], strict=False))
    others = {
        line.split('"')[1].split()[0]
        for path in WORKFLOWS.glob("*.yml")
        if path != NOTICES
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith('- cron: "')
    }
    assert minute not in {part for value in others for part in value.split(",")}, "a minute no other workflow uses"


def test_the_notices_job_has_an_hour_and_its_step_caps_fit_inside_it():
    job = _load(NOTICES)["jobs"]["extract"]
    assert job["timeout-minutes"] == 60
    capped = sum(step.get("timeout-minutes", 0) for step in job["steps"])
    assert capped <= job["timeout-minutes"] - 1, "a minute for checkout, Python and the guards"
    extract = _step(NOTICES, "extract", EXTRACT_STEP)
    (seconds,) = re.findall(r"--read-seconds (\d+)", extract["run"])
    checks = _notices_check_seconds()
    assert int(seconds) == 1800 and checks + int(seconds) <= (extract["timeout-minutes"] - 5) * 60, "minutes left to load"


def test_two_notices_runs_never_overlap_and_never_wait_on_a_publisher():
    notices, conditions = _load(NOTICES), _load(CONDITIONS)
    assert notices["concurrency"] == {"group": "extract-notices", "cancel-in-progress": False}
    assert conditions["concurrency"]["group"] == "publish-data" != notices["concurrency"]["group"]
    assert all("concurrency" not in job for job in notices["jobs"].values()), "one group for the whole run, as a run"


def test_the_notices_job_extracts_into_its_legs_store_copies_it_and_publishes_nothing():
    text = NOTICES.read_text(encoding="utf-8")
    assert "publish.py" not in "\n".join(step.get("run", "") for step in _steps(NOTICES, "extract"))
    for name in ("R2_BUCKET }}", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY }}", "CONDITIONS_DATABASE_URL"):
        assert f"secrets.{name}" not in text, f"{name}: the notices job holds the raw store's key alone"
    extract, serve = _step(NOTICES, "extract", EXTRACT_STEP), _step(NOTICES, "extract", SERVE_STEP)
    assert extract["env"]["LEG"] == serve["env"]["LEG"] == "notices_${{ matrix.data_environment }}"
    assert '-m extract._run --lane "$LEG"' in extract["run"] and "--warehouse" not in extract["run"]
    assert '-m extract._warehouse serve --lane "$LEG"' in serve["run"]
    assert extract["env"]["NPS_API_KEY"] == "${{ secrets.NPS_API_KEY }}", "NPS's alerts are a notices source"
    names = [step.get("name") for step in _steps(NOTICES, "extract")]
    assert names.index(EXTRACT_STEP) < names.index(SERVE_STEP), "copied only after a run that loaded"
    assert serve.get("if") == extract.get("if") == "steps.wanted.outputs.run == 'true'", (
        "a partial extract is still copied; the only condition is decision 92's skip of an unread leg"
    )


def test_the_copy_step_reads_the_run_log_the_extract_step_kept_rather_than_the_store_again():
    """Each run log file is a GET on R2, one more every run, and the copy step used to read them all straight after
    the extract step had."""
    extract, serve = _step(NOTICES, "extract", EXTRACT_STEP), _step(NOTICES, "extract", SERVE_STEP)
    (kept,) = re.findall(r'--run-log-cache "([^"]+)"', extract["run"])
    assert re.findall(r'--run-log-cache "([^"]+)"', serve["run"]) == [kept] and kept.startswith("$RUNNER_TEMP/")


@pytest.mark.parametrize(("status", "outcome", "partial"), [(0, 0, None), (3, 0, "true"), (1, 1, None)])
@pytest.mark.parametrize("name", [EXTRACT_STEP, SERVE_STEP])
def test_a_source_refused_on_its_own_still_lets_the_run_copy_and_then_turns_it_red(tmp_path, name, status, outcome, partial):
    """Exit 3 is extract/_run.py's PARTIAL_EXIT and _warehouse.py serve's: recorded, and red only at the end."""
    record = _stand_in(tmp_path / "extract" / "bin" / "python", status)
    step = _step(NOTICES, "extract", name)
    finished = _run(step["run"], {**_base_env(tmp_path), "LEG": "notices_ua"})
    assert finished.returncode == outcome
    assert _outputs(tmp_path).get("partial") == partial
    assert "--lane notices_ua --raw-bucket raw-bucket" in record.read_text()
    (red,) = [other for other in _steps(NOTICES, "extract") if other.get("if") == f"steps.{step['id']}.outputs.partial == 'true'"]
    assert red["run"].rstrip().endswith("exit 1")


def _production_phone_files_line(text: str) -> list[str]:
    return re.findall(r"^  PRODUCTION_PHONE_FILES: .*$", text, re.M)


def _notices_steps_that_run(tmp_path: Path, leg: str, production_line: str | None) -> tuple[list[str], str]:
    """The names of the notices job's steps that run for `leg` on a schedule from main, with publish-conditions.yml's
    PRODUCTION_PHONE_FILES line made `production_line` (None leaves the line out), and what the steps printed.

    The steps' `if:`s are evaluated in order with the evaluator test_conditions_production_leg_needs_main.py holds to
    GitHub's rules. Every step with an `id` that reads no secret has its own script run under bash, in a copy of the
    repository holding that publish-conditions.yml, so its outputs reach the later `if:`s; the others record nothing,
    as a step whose run asked no question of its output would. A step whose script fails ends the leg there.
    """
    from test_conditions_production_leg_needs_main import _evaluate, _expression

    workflows = tmp_path / leg / ".github" / "workflows"
    workflows.mkdir(parents=True)
    text = CONDITIONS.read_text(encoding="utf-8")
    assert len(_production_phone_files_line(text)) == 1, "publish-conditions.yml has one PRODUCTION_PHONE_FILES line"
    line = "" if production_line is None else f"  PRODUCTION_PHONE_FILES: {production_line}"
    (workflows / CONDITIONS.name).write_text(re.sub(r"^  PRODUCTION_PHONE_FILES: .*$\n?", line and line + "\n", text, flags=re.M))
    context = {
        "github": {"event_name": "schedule", "ref": "refs/heads/main"},
        "inputs": {},
        "matrix": {"data_environment": leg},
        "steps": {},
    }
    ran, printed = [], ""
    for step in _steps(NOTICES, "extract"):
        name = step.get("name") or step.get("uses")
        if "if" in step and not _evaluate(str(step["if"]), context):
            continue
        ran.append(name)
        env = {key: str(value) for key, value in (step.get("env") or {}).items()}
        if "id" not in step or "run" not in step or any("secrets." in value for value in env.values()):
            continue
        env = {key: _evaluate(_expression(value), context) if "${{" in value else value for key, value in env.items()}
        output = tmp_path / leg / f"output_{step['id']}"
        finished = subprocess.run(
            ["bash", "-e", "-c", step["run"]],
            env={**env, "GITHUB_OUTPUT": str(output), "PATH": "/usr/bin:/bin"},
            cwd=tmp_path / leg,
            capture_output=True,
            text=True,
        )
        printed += finished.stdout + finished.stderr
        if finished.returncode != 0:
            return ran, printed + f"\n(exit {finished.returncode})"
        written = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
        context["steps"][step["id"]] = {"outputs": written}
    return ran, printed


def test_the_production_notices_leg_extracts_nothing_while_production_is_on_the_exporters(tmp_path):
    """Decision 92 (the maintainer's poll, 2026-10-06): production's conditions leg stays on the exporters until the
    cutover, and the exporters read no notices store. So the production notices leg asked every club's host and filled
    a store and a served copy every 4 hours for no reader: about 9 runner-minutes and at least 197 upstream requests
    a run (review finding ARC-2 of PR #1805 — dlt → dbt re-platform as one go/no-go change). It is skipped by its own
    condition, read off publish-conditions.yml's line, and says so."""
    ran, printed = _notices_steps_that_run(tmp_path, "production", "exporters")
    assert EXTRACT_STEP not in ran and SERVE_STEP not in ran, f"the production leg ran {ran}"
    assert "::notice title=Production notices leg skipped::" in printed


def test_the_production_notices_leg_runs_once_production_is_on_the_dbt_path(tmp_path):
    """The cutover is changing that one line, and this leg switches on with it: its first run after the cutover
    starts filling the store production's hourly leg reads from then on."""
    ran, printed = _notices_steps_that_run(tmp_path, "production", "dbt")
    assert EXTRACT_STEP in ran and SERVE_STEP in ran, printed
    assert "skipped" not in printed


@pytest.mark.parametrize("production", ["exporters", "dbt"])
def test_the_ua_notices_leg_runs_whatever_production_is_on(tmp_path, production):
    ran, printed = _notices_steps_that_run(tmp_path, "ua", production)
    assert EXTRACT_STEP in ran and SERVE_STEP in ran, printed


@pytest.mark.parametrize("production_line", [None, '"dbt"', "dbt # the cutover", "DBT"])
def test_a_production_line_the_notices_job_cannot_read_stops_its_production_leg_red(tmp_path, production_line):
    """Neither skipped nor run on a guess: a line that is missing, or written in a shape this step does not read, fails
    the leg by name, so a cutover commit that wrote it differently is seen on its first run."""
    ran, printed = _notices_steps_that_run(tmp_path, "production", production_line)
    assert EXTRACT_STEP not in ran and SERVE_STEP not in ran
    assert "::error title=" in printed and printed.rstrip().endswith("(exit 1)"), printed


def test_the_notices_job_reads_the_production_line_publish_conditions_chooses_from():
    """One line is both workflows' switch: the notices job's step names the file and the line the hourly job's
    choice step reads for its production leg."""
    (wanted,) = [step for step in _steps(NOTICES, "extract") if "PRODUCTION_PHONE_FILES" in str(step.get("run", ""))]
    assert ".github/workflows/publish-conditions.yml" in wanted["run"] and wanted.get("working-directory") == "."
    (choose,) = [step for step in _steps(CONDITIONS, "publish") if "PRODUCTION_PHONE_FILES" in str(step.get("run", ""))]
    assert "GITHUB_ENV" in choose["run"]
    names = [step.get("name") or step.get("uses") for step in _steps(NOTICES, "extract")]
    assert names.index("actions/checkout@v7") < names.index(wanted["name"]) < names.index(EXTRACT_STEP)


# --- publish-conditions.yml's dbt path ---------------------------------------


def test_the_hourly_extract_holds_no_notices_key_now_that_nps_is_a_notices_source():
    extract = _step(CONDITIONS, "publish", "Extract this leg's closures and warnings into the raw store (dbt path)")
    assert "NPS_API_KEY" not in extract["env"]


def test_the_hourly_job_adds_its_environments_notices_copy_after_its_own_extract_and_before_the_build():
    names = [step.get("name") for step in _steps(CONDITIONS, "publish")]
    add = _step(CONDITIONS, "publish", ADD_STEP)
    assert names.index("Extract this leg's closures and warnings into the raw store (dbt path)") < names.index(ADD_STEP)
    assert names.index(ADD_STEP) < names.index(BUILD_STEP)
    assert add["env"]["LEG"] == "notices_${{ matrix.data_environment }}" and add["if"] == "env.PHONE_FILES == 'dbt'"
    assert '-m extract._warehouse add-served --lane "$LEG"' in add["run"] and "--warehouse data/warehouse.duckdb" in add["run"]


@pytest.mark.parametrize(
    ("status", "read"), [(0, "latest"), (5, "older"), (6, "none"), (7, "latest"), (1, "unread"), (2, "unread")]
)
def test_the_notices_read_never_stops_the_hourly_publish_and_says_which_copy_it_read(tmp_path, status, read):
    _stand_in(tmp_path / "extract" / "bin" / "python", status)
    finished = _run(_step(CONDITIONS, "publish", ADD_STEP)["run"], {**_base_env(tmp_path), "LEG": "notices_ua"})
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert _outputs(tmp_path) == {"read": read, **({"stale": "true"} if status == 7 else {})}
    assert ("::error title=Notices not read" in finished.stdout) == (read == "unread")


def _served_stale_hours() -> int:
    """extract/_warehouse.py's SERVED_STALE_HOURS, read from its source: this suite installs no dlt."""
    tree = ast.parse((WORKFLOWS.parents[1] / "pipeline" / "extract" / "_warehouse.py").read_text(encoding="utf-8"))
    (value,) = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "SERVED_STALE_HOURS" for target in node.targets)
    ]
    return ast.literal_eval(value)


def test_a_notices_copy_older_than_two_notices_runs_turns_the_hourly_run_red_after_the_publish():
    """Soak run 538 read a copy 3 h 01 min old as `latest` and stayed green, when nothing bounded the age. add-served
    exits 7 past SERVED_STALE_HOURS, twice the notices cron's step, and that is red last."""
    (schedule,) = _load(NOTICES).get("on", _load(NOTICES).get(True))["schedule"]
    cadence = int(schedule["cron"].split()[1].split("/")[1])
    assert _served_stale_hours() == 2 * cadence, "the bound is twice the notices job's cadence"
    add = _step(CONDITIONS, "publish", ADD_STEP)
    assert '--env-file "$GITHUB_ENV"' in add["run"], "the copy's run time reaches the build's dbt commands"
    steps = _steps(CONDITIONS, "publish")
    names = [step.get("name") or step.get("uses") for step in steps]
    (red,) = [step for step in steps if step.get("if") == "steps.notices.outputs.stale == 'true'"]
    assert names.index("Publish to R2") < names.index(red["name"]) and red["run"].rstrip().endswith("exit 1")
    later = steps[names.index(ADD_STEP) + 1 :]
    assert all("OURHIKE_NOTICES_READ_AT" not in str(step.get("env", {})) for step in later), "nothing overrides it"


@pytest.mark.parametrize(("read", "saves"), [("latest", True), ("older", False), ("none", False), ("unread", False), ("", False)])
def test_the_build_saves_no_row_history_unless_it_read_the_newest_notices_copy(tmp_path, read, saves):
    record = _stand_in(tmp_path / "bin" / "python", 0)
    env = {**_base_env(tmp_path), "ENVIRONMENT": "ua", "NOTICES_READ": read}
    finished = _run(_step(CONDITIONS, "publish", BUILD_STEP)["run"], env)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    argv = record.read_text()
    assert argv.startswith("build_marts.py --lane hourly")
    assert ("--no-history-save" not in argv) == saves
    assert _step(CONDITIONS, "publish", BUILD_STEP)["env"]["NOTICES_READ"] == "${{ steps.notices.outputs.read }}"


def test_an_older_or_unread_notices_copy_turns_the_run_red_after_the_publish_and_none_only_warns():
    steps = _steps(CONDITIONS, "publish")
    names = [step.get("name") or step.get("uses") for step in steps]
    (red,) = [step for step in steps if "steps.notices.outputs.read" in str(step.get("if", ""))]
    assert red["if"] == "steps.notices.outputs.read == 'older' || steps.notices.outputs.read == 'unread'"
    assert names.index("Publish to R2") < names.index(red["name"]) and red["run"].rstrip().endswith("exit 1")
