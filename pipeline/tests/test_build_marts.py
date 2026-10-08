"""build_marts.py, the one home of the build order: the command lists it plans for zero, one and two Python steps.

Nothing here runs dbt. The plans are compared argument by argument, and
main() runs against a stand-in for subprocess.run, so what is held is the
order, the selectors and the stop on the first failure, not dbt's answers.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest
import yaml

import build_marts
from build_marts import STEPS, History, Paths, Step, derived_source_problems, plan

PIPELINE_DIR = Path(build_marts.__file__).resolve().parent
DBT_DIR = PIPELINE_DIR / "dbt"
REPO_DIR = PIPELINE_DIR.parent
PATHS = Paths(warehouse=Path("/w/warehouse.duckdb"), processed_dir=Path("/w/processed"), raw_dir=Path("/w/raw"))
STEPS_BY_NAME = {step.name: step for step in STEPS}
DEM_SAMPLING = STEPS_BY_NAME["step_dem_sampling"]
# The two monthly steps STEPS held when the lane tests below were written
# (904f2de1). Those tests spell plan()'s commands out argument by argument,
# which is plan()'s behaviour rather than STEPS', so they run over this fixed
# pair: a step another family adds to STEPS does not rewrite every expected
# argv. The tests that must see the real list (main(), each script's flags, the
# exposures, the derived sources) still read STEPS.
PAIR = [STEPS_BY_NAME["step_dem_sampling"], STEPS_BY_NAME["step_form_route"]]
# Every table STEPS writes, for the tests that run main() over the real STEPS:
# its manifest check refuses a step whose table no source declares.
STEP_TABLES = tuple(step.table for step in STEPS)
# A second step, standing in for tl-net's step_node_lines (pipeline/ELT.md,
# "Python steps, outside dbt"), which writes derived.graph_pieces.
SECOND = Step(name="step_second", table="graph_pieces", command=("step_second.py", "--warehouse", "{warehouse}"))
# A manifest in which no model builds alone. Given it, plan() splits no build,
# as main() plans again once `dbt seed` has written the manifest
# (build_marts.py's docstring, "A MODEL TAGGED `builds_alone`"), so the tests
# of the build's order below spell each build out once. The split has its own
# section, further down.
NONE_ALONE: dict = {}


def argvs(runs):
    return [(run.argv, run.cwd) for run in runs]


#: plan()'s first dbt command (build_marts.py's docstring, "ELEMENTARY'S TABLES ARE BUILT FIRST"), and its first two
#: arguments as the recorded calls list them.
ELEMENTARY_RUN = (("dbt", "run", "--profiles-dir", ".", "--select", "package:elementary"), DBT_DIR)
ELEMENTARY = ("dbt", "run")
#: What every dbt build leaves out, Elementary's checks, and the pass after the writers that runs them, as a build with
#: no lane plans it (build_marts.py's docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS").
NO_CHECKS = "tag:elementary_check"
CHECKS_RUN = (("dbt", "test", "--profiles-dir", ".", "--threads", "1", "-s", NO_CHECKS), DBT_DIR)
#: The writers' pass outside the hourly lane leaves the data-quality writers for a pass of their own (build_marts.py's
#: docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST"), and that pass, in a build with no lane.
QUALITY_WRITERS = ("pub_data_quality", "pub_conditions_data_quality")
WRITERS_RUN = (
    (
        "dbt",
        "build",
        "--profiles-dir",
        ".",
        "--threads",
        "1",
        "-s",
        "path:models/publish",
        "--exclude",
        NO_CHECKS,
        *QUALITY_WRITERS,
    ),
    DBT_DIR,
)
QUALITY_RUN = (("dbt", "build", "--profiles-dir", ".", "-s", *QUALITY_WRITERS, "--exclude", NO_CHECKS), DBT_DIR)


def test_with_no_steps_the_build_is_the_seeds_then_one_build_then_the_writers_then_elementarys_checks():
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=True, manifest=NONE_ALONE)

    assert argvs(runs) == [
        ELEMENTARY_RUN,
        (("dbt", "seed", "--profiles-dir", "."), DBT_DIR),
        (
            (
                "dbt",
                "build",
                "--profiles-dir",
                ".",
                "--exclude",
                "package:dbt_project_evaluator",
                "package:elementary",
                "path:models/publish",
                NO_CHECKS,
            ),
            DBT_DIR,
        ),
        WRITERS_RUN,
        CHECKS_RUN,
        QUALITY_RUN,
    ]


def test_one_step_runs_between_stage_a_and_the_build_of_what_its_table_unblocks():
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True, manifest=NONE_ALONE)

    assert argvs(runs) == [
        ELEMENTARY_RUN,
        (("dbt", "seed", "--profiles-dir", "."), DBT_DIR),
        (
            (
                "dbt",
                "build",
                "--profiles-dir",
                ".",
                "--exclude",
                "package:dbt_project_evaluator",
                "package:elementary",
                "path:models/publish",
                NO_CHECKS,
                "source:derived+",
            ),
            DBT_DIR,
        ),
        (
            (
                "python",
                "step_dem_sampling.py",
                "--warehouse",
                "/w/warehouse.duckdb",
                "--index",
                "/w/raw/elevation/tile_index.json",
            ),
            PIPELINE_DIR,
        ),
        (
            (
                "dbt",
                "build",
                "--profiles-dir",
                ".",
                "-s",
                "source:derived.dem_samples+",
                "--exclude",
                "path:models/publish",
                NO_CHECKS,
            ),
            DBT_DIR,
        ),
        WRITERS_RUN,
        CHECKS_RUN,
        QUALITY_RUN,
    ]


def test_with_two_steps_the_first_steps_build_leaves_the_second_tables_descendants_for_later():
    runs = plan([DEM_SAMPLING, SECOND], dbt="dbt", python="python", paths=PATHS, fixtures=True, manifest=NONE_ALONE)

    assert [run.argv[:2] for run in runs] == [
        ("dbt", "run"),
        ("dbt", "seed"),
        ("dbt", "build"),
        ("python", "step_dem_sampling.py"),
        ("dbt", "build"),
        ("python", "step_second.py"),
        ("dbt", "build"),
        ("dbt", "build"),
        ("dbt", "test"),
        ("dbt", "build"),
    ]
    after_first, after_second = runs[4].argv, runs[6].argv
    assert after_first[after_first.index("-s") :] == (
        "-s",
        "source:derived.dem_samples+",
        "--exclude",
        "path:models/publish",
        NO_CHECKS,
        "source:derived.graph_pieces+",
    )
    assert after_second[after_second.index("-s") :] == (
        "-s",
        "source:derived.graph_pieces+",
        "--exclude",
        "path:models/publish",
        NO_CHECKS,
    )
    assert runs[5].argv == ("python", "step_second.py", "--warehouse", "/w/warehouse.duckdb")
    assert (runs[-3].argv, runs[-3].cwd) == WRITERS_RUN
    assert (runs[-2].argv, runs[-2].cwd) == CHECKS_RUN and (runs[-1].argv, runs[-1].cwd) == QUALITY_RUN


def test_elementary_s_own_tables_build_before_the_seeds_and_stage_a_leaves_the_package_out():
    """With Elementary on and its tables missing, a dbt command records nothing (decision 102, measured on dbt
    2.0.6), the seeds' included, so its tables come first."""
    for lane in (None, "monthly", "hourly"):
        runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane)

        assert (runs[0].label, runs[0].argv, runs[0].cwd) == (build_marts.ELEMENTARY_TABLES, *ELEMENTARY_RUN), lane
        assert runs[1].label == build_marts.SEED, lane
        stage_a = runs[2].argv
        assert "package:elementary" in stage_a[stage_a.index("--exclude") :], lane


def test_without_fixtures_a_step_gets_no_fixture_arguments_and_reads_its_own_defaults():
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=False, manifest=NONE_ALONE)

    assert runs[3].argv == ("python", "step_dem_sampling.py", "--warehouse", "/w/warehouse.duckdb")


def test_threads_reach_every_dbt_seed_and_build_and_no_step_and_the_writers_and_checks_run_at_one():
    runs = plan([DEM_SAMPLING, SECOND], dbt="dbt", python="python", paths=PATHS, fixtures=True, threads=2, manifest=NONE_ALONE)

    for run in runs:
        assert ("--threads" in run.argv) == (run.argv[0] == "dbt"), run.argv
        if run.argv[0] == "dbt":
            expected = "1" if run.stage in (build_marts.WRITERS, build_marts.CHECKS) else "2"
            assert run.argv[run.argv.index("--threads") + 1] == expected, run.argv


def _writers(runs: list[build_marts.Run]) -> build_marts.Run:
    (writers,) = [run for run in runs if run.stage == build_marts.WRITERS]
    return writers


@pytest.mark.parametrize("lane", [None, "monthly"])
def test_the_writers_build_one_at_a_time_outside_the_hourly_lane(lane):
    """Monthly run 25 (refresh-reference.yml 37614075245) ran four network-wide writers side by side out of DuckDB's
    12.4 GiB (build_marts.py's docstring, "THE PUB_ WRITERS BUILD ONE AT A TIME"), so --threads 4 does not reach them."""
    writers = _writers(plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, threads=4))

    assert writers.stage == build_marts.WRITERS
    assert writers.argv[writers.argv.index("--threads") :][:2] == ("--threads", "1")
    assert writers.argv.count("--threads") == 1


def test_the_hourly_lanes_writers_keep_the_builds_threads():
    """Its writers are the files an hourly or daily source reaches, inside publish-conditions.yml's step cap."""
    writers = _writers(plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", threads=4))

    assert writers.stage == build_marts.WRITERS
    assert writers.argv[writers.argv.index("--threads") :][:2] == ("--threads", "4")


def test_the_dbt_and_python_named_are_the_ones_run():
    runs = plan([DEM_SAMPLING], dbt="/venv/dbt/bin/dbt", python="/venv/pipeline/bin/python", paths=PATHS, fixtures=True)

    assert {run.argv[0] for run in runs} == {"/venv/dbt/bin/dbt", "/venv/pipeline/bin/python"}
    assert [run.argv[0] for run in runs].count("/venv/pipeline/bin/python") == 1


def _manifest(*tables: str, other: tuple[str, ...] = ("atc",)) -> dict:
    sources = {f"source.ourhike.derived.{table}": {"name": table, "source_name": "derived"} for table in tables}
    sources |= {f"source.ourhike.{name}.layer": {"name": "layer", "source_name": name} for name in other}
    return {"sources": sources}


def test_derived_sources_and_steps_that_agree_raise_nothing():
    assert derived_source_problems(_manifest("dem_samples"), [DEM_SAMPLING]) == []
    assert derived_source_problems(_manifest(), []) == []


def test_a_derived_source_no_step_writes_is_refused_because_its_models_would_never_build():
    problems = derived_source_problems(_manifest("dem_samples", "graph_pieces"), [DEM_SAMPLING])

    assert problems == [
        "source derived.graph_pieces is declared and no entry of build_marts.STEPS writes it, "
        "so nothing downstream of it would be built"
    ]


def test_a_step_writing_a_table_no_source_declares_is_refused():
    problems = derived_source_problems(_manifest("dem_samples"), [DEM_SAMPLING, SECOND])

    assert problems == ["step_second writes derived.graph_pieces, which no source declares, so dbt would never read it"]


def test_two_steps_writing_one_table_are_refused():
    twin = Step(name="step_twin", table="dem_samples", command=("step_twin.py",))

    assert derived_source_problems(_manifest("dem_samples"), [DEM_SAMPLING, twin]) == [
        "derived.dem_samples is written by more than one step"
    ]


def test_the_projects_derived_sources_are_exactly_the_tables_steps_write():
    declared = []
    for path in sorted((DBT_DIR / "models").rglob("*.yml")):
        for source in yaml.safe_load(path.read_text()).get("sources") or []:
            if source["name"] == "derived":
                declared += [table["name"] for table in source.get("tables") or []]

    assert sorted(declared) == sorted(step.table for step in STEPS)


@pytest.mark.parametrize("step", STEPS, ids=lambda step: step.name)
def test_each_step_script_takes_every_flag_its_entry_gives_it(step):
    help_text = subprocess.run(
        [sys.executable, step.command[0], "--help"], cwd=PIPELINE_DIR, capture_output=True, text=True, check=True
    ).stdout

    given = step.command[1:] + step.fixture_args + tuple(argument for _, args in step.lane_args for argument in args)
    for flag in (argument for argument in given if argument.startswith("--")):
        assert re.search(rf"(^|\s|\[){re.escape(flag)}\b", help_text), f"{step.command[0]} --help names no {flag}"


def test_the_monthly_lane_lands_the_water_scans_its_build_job_pinned_and_fixtures_land_their_own():
    """#1652: refresh-reference.yml's build job scans the Geofabrik extracts the raw store keeps and pins the scans as
    derived/osm_water.geojson and derived/trail_water.json; build_marts.py --lane monthly names exactly those, and the
    fixture build and the hourly lane never do."""

    def args_of(name: str, **options) -> tuple[str, ...]:
        (run,) = [run for run in plan(STEPS, dbt="dbt", python="python", paths=PATHS, **options) if run.label == name]
        return run.argv[2:]

    assert args_of("step_osm_water", fixtures=False, lane="monthly")[2:] == ("--landed", "/w/raw/derived/osm_water.geojson")
    assert args_of("step_site_water", fixtures=False, lane="monthly")[2:] == ("--from-file", "/w/raw/derived/trail_water.json")
    assert args_of("step_osm_water", fixtures=True, lane="monthly")[2:] == ("--points", "/w/raw/osm_water/points.geojson")
    assert args_of("step_osm_water", fixtures=False)[2:] == ()


class _Recorder:
    """subprocess.run as main() calls it: every command it was asked to run, answered with the given exit codes."""

    def __init__(self, codes: dict[int, int] | None = None):
        self.calls: list[tuple[tuple[str, ...], Path, dict]] = []
        self.codes = codes or {}

    def __call__(self, argv, *, cwd, env, check):
        self.calls.append((tuple(argv), cwd, env))
        return subprocess.CompletedProcess(argv, self.codes.get(len(self.calls), 0))


def _answer_retries(recorder, retry_codes: list[int] | None = None):
    """subprocess.run as `recorder` answers it, with every `dbt retry` (build_marts.py's docstring, "A FAILED dbt
    BUILD IS RETRIED") answered apart: from `retry_codes` in turn, else as the build before it ended, leaving its
    run_results.json as it was, which is a failure that is not chance. The retries are kept in `recorder.retries`, so
    `recorder.calls` stays the commands the plan holds."""
    recorder.retries = []
    codes = list(retry_codes or [])
    last = {"code": 0}

    def answer(argv, *, cwd, env, check):
        if tuple(argv[1:2]) == ("retry",):
            recorder.retries.append(tuple(argv))
            return subprocess.CompletedProcess(argv, codes.pop(0) if codes else last["code"])
        completed = recorder(argv, cwd=cwd, env=env, check=check)
        last["code"] = completed.returncode
        return completed

    return answer


def _main(
    monkeypatch,
    tmp_path,
    manifest: dict,
    codes: dict[int, int] | None = None,
    extra: tuple[str, ...] = (),
    recorder: _Recorder | None = None,
) -> tuple[int, _Recorder]:
    recorder = recorder or _Recorder(codes)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(build_marts, "MANIFEST_PATH", tmp_path / "manifest.json")
    # So no dbt run's results but a test's own are ever read (the repository's target/ may hold a real build's).
    monkeypatch.setattr(build_marts, "RUN_RESULTS_PATH", tmp_path / "run_results.json")
    monkeypatch.setattr(build_marts.subprocess, "run", _answer_retries(recorder))
    # So built_by() asks git nothing: the recorder stands in for every subprocess.run.
    monkeypatch.setenv("OURHIKE_BUILT_BY", "abc123 run 7.1")
    code = build_marts.main(
        [
            "--fixtures",
            "--dbt",
            "dbt",
            "--python",
            "python",
            "--warehouse",
            str(tmp_path / "warehouse.duckdb"),
            "--processed-dir",
            str(tmp_path / "processed"),
            "--raw-dir",
            str(tmp_path / "raw"),
            "--history-url",
            str(tmp_path / "history"),
            "--history-python",
            "python",
            *extra,
        ]
    )
    return code, recorder


def _history(tmp_path: Path) -> History:
    """The store _main() names: not in row_history_stores.toml, so an empty one may start its history."""
    return History(str(tmp_path / "history"), True, "python")


#: The restore's first two arguments: main() runs it before anything else.
RESTORE = ("python", "row_history.py")


def test_main_runs_the_plan_in_order_with_one_warehouse_for_dbt_and_the_steps(monkeypatch, tmp_path):
    manifest = _manifest(*STEP_TABLES)
    code, recorder = _main(monkeypatch, tmp_path, manifest)

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    assert code == 0
    assert [(argv, cwd) for argv, cwd, _ in recorder.calls] == argvs(
        plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True, history=_history(tmp_path), manifest=manifest)
    )
    assert recorder.calls[0][0][:3] == (*RESTORE, "restore") and recorder.calls[-1][0][:3] == (*RESTORE, "save")
    for _, _, env in recorder.calls:
        assert env["OURHIKE_WAREHOUSE"] == str(tmp_path / "warehouse.duckdb")
        assert env["OURHIKE_PROCESSED_DIR"] == str(tmp_path / "processed")
        assert env["TZ"] == "UTC", "macros/row_hash.sql: a TIMESTAMPTZ hashes in the session's zone"
    assert (tmp_path / "processed").is_dir(), "COPY creates no directory, so the writers' folder must exist first"


def test_every_command_runs_with_elementary_on(monkeypatch, tmp_path):
    """dbt_project.yml's switch (decision 102): on for everything build_marts.py runs, off for the pytest suites."""
    _, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES))

    assert {env.get("OURHIKE_ELEMENTARY") for _, _, env in recorder.calls} == {"true"}


def test_main_stops_at_the_first_command_that_fails_and_answers_with_its_exit_code(monkeypatch, tmp_path):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={4: 2})

    assert code == 2
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ELEMENTARY, ("dbt", "seed"), ("dbt", "build")]
    assert not [argv for argv, _, _ in recorder.calls if argv[2:3] == ("save",)], "a failed build never saves"


# --- A failed dbt build is retried (build_marts.py's docstring, "A FAILED dbt BUILD IS RETRIED") ---


def _retrying_main(monkeypatch, tmp_path, retry_codes, extra=()):
    """_main() with stage A's build (the fourth command) failing, and its `dbt retry`s answered from `retry_codes`."""
    recorder = _Recorder({4: 1})
    original = _answer_retries
    monkeypatch.setattr(sys.modules[__name__], "_answer_retries", lambda each: original(each, retry_codes))
    return _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), extra=extra, recorder=recorder)


def test_a_failed_dbt_build_is_retried_at_one_thread_and_the_build_carries_on_once_a_retry_passes(monkeypatch, tmp_path, capsys):
    """Monthly run 26 (refresh-reference.yml 37649648453) failed on a node run 25 had built, twice: the maintainer's
    answer was dbt's own `retry`, up to 3 times."""
    code, recorder = _retrying_main(monkeypatch, tmp_path, [1, 0])

    assert code == 0
    assert recorder.retries == [("dbt", "retry", "--profiles-dir", ".", "--threads", "1")] * 2
    assert [argv[:2] for argv, _, _ in recorder.calls][3] == ("dbt", "build")
    assert any(argv[2:3] == ("save",) for argv, _, _ in recorder.calls), "the build went on to the writers and the save"
    out = capsys.readouterr().out
    assert "dbt retry 1/3" in out and "dbt retry 2/3" in out and "passed on retry 2" in out


def test_a_dbt_build_still_failing_after_three_retries_stops_the_build(monkeypatch, tmp_path):
    code, recorder = _retrying_main(monkeypatch, tmp_path, [1, 1, 1, 0])

    assert code == 1
    assert len(recorder.retries) == build_marts.DBT_RETRIES == 3
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ELEMENTARY, ("dbt", "seed"), ("dbt", "build")]


def test_a_failed_python_step_or_seed_is_never_retried(monkeypatch, tmp_path):
    for codes in ({1: 1}, {2: 1}, {3: 1}):
        recorder = _Recorder(codes)
        code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), recorder=recorder)
        assert code != 0 and recorder.retries == [], codes


def test_the_hourly_lane_retries_a_failed_build_three_times_with_the_builds_indirect_selection(monkeypatch, tmp_path):
    """The maintainer, 2026-10-07: "The hourly lane should get the same retry logic", and then, of a deadline inside
    publish-conditions.yml's 6 minutes, "do up to 3 retries. period". Without --state the hourly build takes its
    lane's parents with `--indirect-selection cautious`, and a retry that dropped it would test them all eagerly."""
    recorder = _Recorder({4: 1})
    # So the build reaches stage A: _manifest() holds no step_<name> exposure for lane_problems() to read.
    monkeypatch.setattr(build_marts, "lane_problems", lambda manifest, steps, lane: [])
    code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), extra=("--lane", "hourly"), recorder=recorder)

    assert code == 1
    build = recorder.calls[3][0]
    assert build[:2] == ("dbt", "build") and build[-2:] == ("--indirect-selection", "cautious")
    retry = ("dbt", "retry", "--profiles-dir", ".", "--threads", "1", "--indirect-selection", "cautious")
    assert recorder.retries == [retry] * build_marts.DBT_RETRIES


def test_a_deferred_build_is_retried_without_its_state():
    """Given `--state`, dbt 2.0.6's retry read that directory's run_results.json and found nothing to retry; without
    it, a retry after a `--defer --state` build re-ran the failed model and the nodes it skipped (measured
    2026-10-07)."""
    build = ("dbt", "build", "--profiles-dir", "p", "--threads", "4", "-s", "x+", "--defer", "--state", "monthly/target")

    assert build_marts.retry_argv(build_marts.Run("stage A", build, build_marts.DBT_DIR, build_marts.STAGE_A)) == (
        "dbt",
        "retry",
        "--profiles-dir",
        "p",
        "--threads",
        "1",
    )


def test_after_a_retry_run_results_hold_every_node_the_build_ran_with_its_last_result(monkeypatch, tmp_path):
    """A retry's own run_results.json holds only the nodes it retried, so a test that warned and holds a source in
    the first attempt would otherwise be lost once a retry passed."""
    results = tmp_path / "run_results.json"
    results.write_text(
        json.dumps(
            {
                "metadata": {"invocation_id": "first"},
                "results": [
                    {"unique_id": "model.ourhike.a", "status": "success"},
                    {"unique_id": "test.ourhike.holds", "status": "warn"},
                    {"unique_id": "model.ourhike.oom", "status": "error"},
                    {"unique_id": "model.ourhike.below", "status": "skipped"},
                ],
            }
        )
    )

    def retry(argv, *, cwd, env, check):
        results.write_text(
            json.dumps(
                {
                    "metadata": {"invocation_id": "retry"},
                    "results": [
                        {"unique_id": "model.ourhike.oom", "status": "success"},
                        {"unique_id": "model.ourhike.below", "status": "success"},
                    ],
                }
            )
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(build_marts.subprocess, "run", retry)
    run = build_marts.Run("stage A", ("dbt", "build", "--profiles-dir", "."), build_marts.DBT_DIR)
    completed = build_marts.retry_failed_build(run, {}, subprocess.CompletedProcess(run.argv, 1), results)

    assert completed.returncode == 0
    merged = json.loads(results.read_text())
    assert {each["unique_id"]: each["status"] for each in merged["results"]} == {
        "model.ourhike.a": "success",
        "test.ourhike.holds": "warn",
        "model.ourhike.oom": "success",
        "model.ourhike.below": "success",
    }


def test_main_refuses_after_the_seeds_when_a_derived_source_has_no_step(monkeypatch, tmp_path, capsys):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES, "unwritten"))

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ELEMENTARY, ("dbt", "seed")]
    assert "source derived.unwritten is declared and no entry of build_marts.STEPS writes it" in capsys.readouterr().out


def _dbt_job() -> dict:
    workflow = yaml.safe_load((REPO_DIR / ".github" / "workflows" / "pipeline-tests.yml").read_text())
    return workflow["jobs"]["dbt"]


def _local_imports(start: Path) -> set[Path]:
    """start and every pipeline/ module it imports, followed through their own imports."""
    seen: set[Path] = set()
    queue = [start]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for name in names:
                candidate = PIPELINE_DIR.joinpath(*name.split(".")).with_suffix(".py")
                if candidate.exists():
                    queue.append(candidate)
    return seen


def test_the_dbt_jobs_scope_covers_build_marts_and_every_step_with_what_they_import():
    scope = next(step for step in _dbt_job()["steps"] if step.get("id") == "scope")["with"]["paths"].split()
    files = _local_imports(PIPELINE_DIR / "build_marts.py")
    for step in STEPS:
        files |= _local_imports(PIPELINE_DIR / step.command[0])

    uncovered = sorted(
        relative
        for relative in (str(path.relative_to(REPO_DIR)) for path in files)
        if not any(relative.startswith(prefix) for prefix in scope)
    )
    assert not uncovered, f"run by the dbt job's build and outside its paths: {uncovered}"


#: A pipeline/ file a step's command names: a script, a test file, a requirements file.
NAMED_FILE = re.compile(r"(?<![\w/.-])((?:\.\./)?[\w/.-]+\.(?:py|txt|toml))\b")
#: `python -m <module>` for a module of the pipeline's own, not pytest.
NAMED_MODULE = re.compile(r"-m ((?!pytest\b)[a-z_][\w.]*)")


def test_the_dbt_jobs_scope_covers_every_file_its_steps_read():
    """Every pipeline/ file a dbt-job step names, with what its Python imports, and what every pytest run loads.

    WF6 of the PR #1805 review: the three pytest steps load tests/conftest.py, whose autouse fixtures apply to them,
    and pyproject.toml, whose `pythonpath = ["."]` is what lets `import row_history` work; the row-dates step greps
    its pytest pin out of requirements-dev.txt; and make_dbt_fixtures.py imports load_raw.py. None was in the list,
    so a pull request touching only one of them skipped the one job that runs those tests (the pytest job skips
    them without OURHIKE_DBT)."""
    job = _dbt_job()
    scope = next(step for step in job["steps"] if step.get("id") == "scope")["with"]["paths"].split()
    default = REPO_DIR / job["defaults"]["run"]["working-directory"]
    files: set[Path] = set()
    for step in job["steps"]:
        run = step.get("run") or ""
        where = REPO_DIR / step["working-directory"] if "working-directory" in step else default
        named = [(where / name).resolve() for name in NAMED_FILE.findall(run)]
        named += [PIPELINE_DIR.joinpath(*module.split(".")).with_suffix(".py") for module in NAMED_MODULE.findall(run)]
        if "-m pytest" in run:
            named += [PIPELINE_DIR / "tests" / "conftest.py", PIPELINE_DIR / "pyproject.toml"]
        for path in named:
            if path.is_file() and path.is_relative_to(PIPELINE_DIR):
                files |= _local_imports(path) if path.suffix == ".py" else {path}

    assert PIPELINE_DIR / "make_dbt_fixtures.py" in files, "the walk did not reach the steps' own scripts"
    uncovered = sorted(
        relative
        for relative in (str(path.relative_to(REPO_DIR)) for path in files)
        if not any(relative.startswith(prefix) for prefix in scope)
    )
    assert not uncovered, f"read by the dbt job's steps and outside its paths: {uncovered}"


def test_ci_and_test_sh_build_only_through_build_marts_apart_from_the_evaluator():
    runs = [step.get("run") or "" for step in _dbt_job()["steps"]]
    assert sum("build_marts.py --fixtures" in run for run in runs) == 1
    assert not [run for run in runs if re.search(r"\bdbt seed\b", run)]
    assert not [run for run in runs if re.search(r"\bdbt build\b", run) and "package:dbt_project_evaluator" not in run]

    test_sh = (REPO_DIR / "scripts" / "test.sh").read_text()
    assert "build_marts.py --fixtures" in test_sh
    dbt_lines = [line for line in test_sh.splitlines() if '"${dbt_cmd[@]}" seed' in line or '"${dbt_cmd[@]}" build' in line]
    assert all("package:dbt_project_evaluator" in line for line in dbt_lines), dbt_lines


# --- The lanes (build_marts.py's docstring, "A LANE BUILDS ONLY ITS OWN NODES") ---


def test_the_monthly_lane_is_the_whole_plan_with_every_hourly_or_daily_node_excluded_from_each_dbt_build():
    runs = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly", manifest=NONE_ALONE)
    everything = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False, manifest=NONE_ALONE)

    assert [run.label for run in runs] == [run.label for run in everything]
    for lane_run, full_run in zip(runs, everything, strict=True):
        if full_run.stage == build_marts.CHECKS:
            # The monthly lane's training window rides on its checks pass alone (build_marts.MONTHLY_TRAINING_DAYS).
            assert lane_run.argv == full_run.argv + (
                "--exclude",
                *build_marts.LANE_EXCLUDES,
                "--vars",
                json.dumps({"days_back": build_marts.MONTHLY_TRAINING_DAYS}),
            )
        elif full_run.stage == build_marts.DATA_QUALITY:
            expected = (
                "dbt",
                "build",
                "--profiles-dir",
                ".",
                "-s",
                "pub_data_quality",
                "--exclude",
                NO_CHECKS,
                *build_marts.LANE_EXCLUDES,
            )
            assert lane_run.argv == expected, "its lane's writer alone"
        elif full_run.argv[:2] != ("dbt", "build"):
            assert lane_run.argv == full_run.argv, "the seeds and the Python steps are the same in every lane"
        else:
            assert "--exclude" in full_run.argv, "every build leaves Elementary's checks out"
            assert lane_run.argv == full_run.argv + build_marts.LANE_EXCLUDES


def test_the_monthly_lanes_writers_leave_the_hourly_writers_unrun():
    writers = _writers(plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly"))

    assert writers.argv == (
        "dbt",
        "build",
        "--profiles-dir",
        ".",
        "--threads",
        "1",
        "-s",
        "path:models/publish",
        "--exclude",
        NO_CHECKS,
        *QUALITY_WRITERS,
        "config.meta.cadence:hourly+",
        "config.meta.cadence:daily+",
    )


# An hourly step, standing in for cw2's step_weather_squares (WN03): the NWS
# alerts' placement reads its table, and every node it unblocks is hourly.
SQUARES = Step(
    name="step_weather_squares",
    table="weather_squares",
    command=("step_weather_squares.py", "--warehouse", "{warehouse}"),
    lane="hourly",
)


def test_the_hourly_lane_with_nothing_to_defer_to_builds_its_nodes_and_their_parents_then_its_writers():
    runs = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly")

    assert argvs(runs) == [
        ELEMENTARY_RUN,
        (("dbt", "seed", "--profiles-dir", "."), DBT_DIR),
        (
            (
                "dbt",
                "build",
                "--profiles-dir",
                ".",
                "-s",
                "config.meta.cadence:hourly+",
                "config.meta.cadence:daily+",
                "+config.meta.cadence:hourly",
                "+config.meta.cadence:daily",
                "--exclude",
                "package:dbt_project_evaluator",
                "package:elementary",
                "path:models/publish",
                NO_CHECKS,
                "source:derived.dem_samples+",
                "source:derived.formed_routes+",
                "--indirect-selection",
                "cautious",
            ),
            DBT_DIR,
        ),
        (
            (
                "dbt",
                "build",
                "--profiles-dir",
                ".",
                "-s",
                "path:models/publish,config.meta.cadence:hourly+",
                "path:models/publish,config.meta.cadence:daily+",
                "--exclude",
                NO_CHECKS,
                "source:derived.dem_samples+",
                "source:derived.formed_routes+",
                "--indirect-selection",
                "cautious",
            ),
            DBT_DIR,
        ),
        # Neither the checks pass nor the data-quality file: both are the checks run's, after the build has published
        # (build_marts.py's docstring, "THE HOURLY LANE'S CHECKS RUN APART").
    ]


def test_the_hourly_lane_defers_every_build_to_the_state_it_is_given_and_takes_no_parents():
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", state=Path("/m/target"))

    for run in runs[2:]:
        if run.argv[0] == "python":
            assert "--defer" not in run.argv, "a Python step reads the warehouse; it has nothing to defer"
            continue
        assert run.argv[-3:] == ("--defer", "--state", "/m/target"), run.argv
        assert not set(build_marts.LANE_PARENTS) & set(run.argv), run.argv
        assert "--indirect-selection" not in run.argv
    assert "--defer" not in runs[0].argv + runs[1].argv, "Elementary's tables and dbt seed have nothing to defer to"


def test_an_hourly_step_runs_in_the_hourly_lane_and_no_monthly_step_does():
    runs = plan([*PAIR, SQUARES], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly")

    assert [run.label for run in runs if run.argv[0] == "python"] == ["step_weather_squares"]
    stage_a, unblocked = runs[2].argv, runs[4].argv
    assert "source:derived+" in stage_a, "stage A leaves every derived table's descendants for after its step"
    assert unblocked[unblocked.index("-s") :] == (
        "-s",
        "source:derived.weather_squares+",
        "--exclude",
        "path:models/publish",
        NO_CHECKS,
        "source:derived.dem_samples+",
        "source:derived.formed_routes+",
        "--indirect-selection",
        "cautious",
    )


def test_the_monthly_lane_leaves_an_hourly_step_out_with_everything_its_table_unblocks():
    runs = plan([*PAIR, SQUARES], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly")

    assert [run.label for run in runs if run.argv[0] == "python"] == [step.name for step in PAIR]
    for run in runs:
        if run.argv[:2] == ("dbt", "build"):
            assert "source:derived.weather_squares+" in run.argv, run.argv


def test_without_step_leaves_the_step_out_and_its_writers_unrun_so_publish_keeps_their_last_files():
    runs = plan(
        [*PAIR, SQUARES],
        dbt="dbt",
        python="python",
        paths=PATHS,
        fixtures=False,
        lane="hourly",
        without=("step_weather_squares",),
    )

    assert not [run for run in runs if run.argv[0] == "python"]
    writers = _writers(runs).argv
    assert writers[writers.index("--exclude") :][:5] == (
        "--exclude",
        NO_CHECKS,
        "source:derived.dem_samples+",
        "source:derived.formed_routes+",
        "source:derived.weather_squares+",
    )


def test_without_step_leaves_the_steps_table_unbuilt_in_a_build_with_no_lane_too():
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=True, without=("step_form_route",))

    assert [run.label for run in runs if run.argv[0] == "python"] == [
        step.name for step in STEPS if step.name != "step_form_route"
    ]
    for run in runs:
        if run.argv[:2] == ("dbt", "build"):
            assert "source:derived.formed_routes+" in run.argv, run.argv


def test_without_step_naming_no_step_is_refused_rather_than_building_everything():
    with pytest.raises(ValueError, match="names no entry of STEPS: step_typo"):
        plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", without=("step_typo",))


@pytest.mark.parametrize("lane", [None, "monthly"])
def test_state_outside_the_hourly_lane_is_refused_because_nothing_else_defers(lane):
    with pytest.raises(ValueError, match="hourly lane's"):
        plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, state=Path("/m/target"))


def test_a_lane_this_file_does_not_know_is_refused():
    with pytest.raises(ValueError, match="no lane 'weekly'"):
        plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="weekly")


def _lane_manifest(step_reads: dict[str, list[str]], unblocks: dict[str, list[str]] | None = None) -> dict:
    """An hourly, a monthly and a daily source, each feeding a model, a step exposure per entry of step_reads, and
    under `unblocks` the models each derived table feeds."""
    manifest = _manifest(*STEP_TABLES, *(table for table in (unblocks or {}) if table not in STEP_TABLES))
    manifest["sources"] |= {
        "source.ourhike.ourhike.raw_ourhike__closures": {
            "name": "raw_ourhike__closures",
            "config": {"meta": {"cadence": "hourly"}},
        },
        "source.ourhike.atc.raw_atc__centerline": {"name": "raw_atc__centerline", "config": {"meta": {"cadence": "monthly"}}},
        "source.ourhike.nynjtc.raw_terms": {"name": "raw_terms", "config": {"meta": {"cadence": "daily"}}},
    }
    manifest["child_map"] = {
        "source.ourhike.ourhike.raw_ourhike__closures": ["model.ourhike.int_closures__unioned"],
        "model.ourhike.int_closures__unioned": ["model.ourhike.closures"],
        "source.ourhike.atc.raw_atc__centerline": ["model.ourhike.int_elevation__sample_points"],
        "source.ourhike.nynjtc.raw_terms": ["model.ourhike.int_warnings__terms"],
        **{f"source.ourhike.derived.{table}": nodes for table, nodes in (unblocks or {}).items()},
    }
    manifest["exposures"] = {
        f"exposure.ourhike.{name}": {"name": name, "depends_on": {"nodes": nodes}} for name, nodes in step_reads.items()
    }
    return manifest


def test_faster_nodes_follow_every_hourly_and_daily_source_down_to_what_it_reaches():
    reached = build_marts.faster_nodes(_lane_manifest({}))

    assert reached == {
        "source.ourhike.ourhike.raw_ourhike__closures",
        "model.ourhike.int_closures__unioned",
        "model.ourhike.closures",
        "source.ourhike.nynjtc.raw_terms",
        "model.ourhike.int_warnings__terms",
    }


def test_a_lane_passes_a_step_whose_exposure_reads_only_monthly_nodes():
    manifest = _lane_manifest(
        {step.name: ["model.ourhike.int_elevation__sample_points"] for step in STEPS if not step.reads_no_model}
    )

    for lane in build_marts.LANES:
        assert build_marts.lane_problems(manifest, STEPS, lane) == []


@pytest.mark.parametrize("lane", ["monthly", "hourly"])
@pytest.mark.parametrize("node", ["model.ourhike.closures", "model.ourhike.int_warnings__terms"])
def test_a_lane_refuses_a_monthly_step_that_reads_a_node_an_hourly_or_daily_source_reaches(lane, node):
    manifest = _lane_manifest({**{step.name: [] for step in STEPS}, DEM_SAMPLING.name: [node]})

    problems = build_marts.lane_problems(manifest, STEPS, lane)

    assert problems == [
        f"{DEM_SAMPLING.name} reads {node}, which an hourly or daily source reaches: the monthly lane, where the step "
        "runs, does not build it, so the step would read a stale or missing input"
    ]


# Each derived table below feeds its own staging model first, as stg_derived__weather_squares does: a model no
# source with a cadence reaches, whose lane is the lane of the writer it ends in.
HOURLY_WRITER = "model.ourhike.pub_conditions_closures"
MONTHLY_WRITER = "model.ourhike.pub_trails_geojson"


def _writers_manifest(steps: list[Step], feeds: str) -> dict:
    manifest = _lane_manifest(
        {step.name: [] for step in steps}, unblocks={"weather_squares": ["model.ourhike.stg_derived__weather_squares"]}
    )
    manifest["child_map"] |= {
        "model.ourhike.stg_derived__weather_squares": [feeds],
        "model.ourhike.closures": [HOURLY_WRITER],
        "model.ourhike.int_elevation__sample_points": [MONTHLY_WRITER],
    }
    return manifest


def test_a_lane_passes_an_hourly_step_whose_table_feeds_only_hourly_writers():
    manifest = _writers_manifest([*PAIR, SQUARES], feeds="model.ourhike.closures")

    for lane in build_marts.LANES:
        assert build_marts.lane_problems(manifest, [*PAIR, SQUARES], lane) == []


def test_a_lane_refuses_a_monthly_step_whose_table_feeds_only_the_hourly_lanes_writers():
    monthly_squares = Step(name="step_weather_squares", table="weather_squares", command=("step_weather_squares.py",))
    manifest = _writers_manifest([*PAIR, monthly_squares], feeds="model.ourhike.closures")

    assert build_marts.lane_problems(manifest, [*PAIR, monthly_squares], "monthly") == [
        "step_weather_squares runs in the monthly lane, and every writer derived.weather_squares feeds is the hourly "
        f"lane's ({HOURLY_WRITER}): give its STEPS entry lane=HOURLY"
    ]


def test_a_lane_refuses_an_hourly_step_whose_table_feeds_a_monthly_writer():
    manifest = _writers_manifest([*PAIR, SQUARES], feeds="model.ourhike.int_elevation__sample_points")

    assert build_marts.lane_problems(manifest, [*PAIR, SQUARES], "hourly") == [
        "step_weather_squares runs in the hourly lane, and derived.weather_squares feeds monthly-lane writers "
        f"({MONTHLY_WRITER}), which no hourly or daily source reaches: the monthly lane leaves out what an hourly "
        "step unblocks, so nothing would write them"
    ]


def test_a_lane_refuses_a_step_with_no_exposure_naming_its_inputs_and_no_lane_does_not_ask():
    manifest = _lane_manifest({})

    assert build_marts.lane_problems(manifest, [DEM_SAMPLING], "monthly") == [
        f"{DEM_SAMPLING.name} has no exposure named {DEM_SAMPLING.name} listing what it reads, so the monthly lane "
        "cannot check that it builds the step's inputs"
    ]
    assert build_marts.lane_problems(manifest, [DEM_SAMPLING], None) == []


def test_main_refuses_after_the_seeds_when_the_monthly_lane_would_leave_a_steps_input_unbuilt(monkeypatch, tmp_path, capsys):
    manifest = _lane_manifest({**{step.name: [] for step in STEPS}, DEM_SAMPLING.name: ["model.ourhike.closures"]})

    code, recorder = _main(monkeypatch, tmp_path, manifest, extra=("--lane", "monthly"))

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ELEMENTARY, ("dbt", "seed")]
    assert f"{DEM_SAMPLING.name} reads model.ourhike.closures" in capsys.readouterr().out


def test_main_runs_the_monthly_lanes_plan_when_every_step_reads_monthly_nodes(monkeypatch, tmp_path):
    manifest = _lane_manifest(
        {step.name: ["model.ourhike.int_elevation__sample_points"] for step in STEPS if not step.reads_no_model}
    )

    code, recorder = _main(monkeypatch, tmp_path, manifest, extra=("--lane", "monthly"))

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    assert code == 0
    assert [(argv, cwd) for argv, cwd, _ in recorder.calls] == argvs(
        plan(
            STEPS,
            dbt="dbt",
            python="python",
            paths=paths,
            fixtures=True,
            lane="monthly",
            history=_history(tmp_path),
            manifest=manifest,
        )
    )


def test_every_step_names_what_it_reads_in_an_exposure_of_its_own_name():
    """The lanes' check reads each step's inputs off its step_<name> exposure, so a step without one refuses every lane build."""
    exposures = {}
    for path in sorted((DBT_DIR / "models").rglob("*.yml")):
        for exposure in yaml.safe_load(path.read_text()).get("exposures") or []:
            exposures[exposure["name"]] = exposure

    for step in STEPS:
        if step.reads_no_model:
            continue
        assert step.name in exposures, f"no exposure named {step.name} lists what {step.command[0]} reads"
        assert exposures[step.name].get("depends_on"), f"exposure {step.name} names no input"


def test_a_step_that_reads_no_model_needs_no_exposure_in_either_lane():
    file_only = Step(name="step_weather_squares", table="weather_squares", command=("x.py",), lane="hourly", reads_no_model=True)
    manifest = _writers_manifest(PAIR, feeds="model.ourhike.closures")

    for lane in build_marts.LANES:
        assert build_marts.lane_problems(manifest, [*PAIR, file_only], lane) == []


def test_a_step_that_says_it_reads_no_model_and_whose_exposure_lists_one_is_refused():
    file_only = Step(name="step_weather_squares", table="weather_squares", command=("x.py",), lane="hourly", reads_no_model=True)
    manifest = _writers_manifest(PAIR, feeds="model.ourhike.closures")
    manifest["exposures"]["exposure.ourhike.step_weather_squares"] = {
        "name": "step_weather_squares",
        "depends_on": {"nodes": ["model.ourhike.closures"]},
    }

    assert build_marts.lane_problems(manifest, [*PAIR, file_only], "hourly") == [
        "step_weather_squares says it reads no dbt node (reads_no_model), and its exposure step_weather_squares lists some"
    ]


# --- The models that build alone (build_marts.py's docstring, "A MODEL TAGGED `builds_alone`") ---

ALONE, BELOW = "tag:builds_alone", "tag:builds_alone+"
STAGE_A_EXCLUDES = (
    "package:dbt_project_evaluator",
    "package:elementary",
    "path:models/publish",
    NO_CHECKS,
    "source:derived+",
)


def test_stage_a_has_no_dash_s_so_its_passes_select_the_tag_itself_the_tagged_ones_on_one_thread():
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True, threads=4)

    assert [(run.label, run.argv) for run in runs[2:5]] == [
        (
            "stage A: everything no Python step reads back: all but the models that build alone and what they feed",
            ("dbt", "build", "--profiles-dir", ".", "--threads", "4", "--exclude", *STAGE_A_EXCLUDES, BELOW),
        ),
        (
            "stage A: everything no Python step reads back: the models that build alone, one at a time",
            ("dbt", "build", "--profiles-dir", ".", "--threads", "1", "-s", ALONE, "--exclude", *STAGE_A_EXCLUDES),
        ),
        (
            "stage A: everything no Python step reads back: what the models that build alone feed",
            ("dbt", "build", "--profiles-dir", ".", "--threads", "4", "-s", BELOW, "--exclude", *STAGE_A_EXCLUDES, ALONE),
        ),
    ]


def test_what_a_monthly_steps_table_unblocks_is_split_with_each_pass_inside_the_steps_own_selection():
    runs = plan([DEM_SAMPLING, SECOND], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly")

    passes = [run for run in runs if run.label.startswith("what derived.dem_samples unblocks")]
    excludes = ("path:models/publish", NO_CHECKS, "source:derived.graph_pieces+", *build_marts.LANE_EXCLUDES)
    assert [run.argv for run in passes] == [
        ("dbt", "build", "--profiles-dir", ".", "-s", "source:derived.dem_samples+", "--exclude", *excludes, BELOW),
        (
            ("dbt", "build", "--profiles-dir", ".", "--threads", "1", "-s", "source:derived.dem_samples+,tag:builds_alone")
            + ("--exclude", *excludes)
        ),
        (
            ("dbt", "build", "--profiles-dir", ".", "-s", "source:derived.dem_samples+,tag:builds_alone+", "--exclude")
            + (*excludes, ALONE)
        ),
    ]
    assert [run.label for run in passes] == [
        "what derived.dem_samples unblocks: all but the models that build alone and what they feed",
        "what derived.dem_samples unblocks: the models that build alone, one at a time",
        "what derived.dem_samples unblocks: what the models that build alone feed",
    ]


@pytest.mark.parametrize("state", [None, Path("/m/target")], ids=["no state", "deferred"])
def test_the_hourly_lane_splits_no_build_because_its_six_minute_step_has_no_room(state):
    runs = plan([*PAIR, SQUARES], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", state=state)

    assert not [run.argv for run in runs if any(build_marts.BUILDS_ALONE in argument for argument in run.argv)]
    # What the squares unblock, then the writers: the data-quality file is the checks run's (HOURLY_LANE_CHECKS).
    assert [run.argv[:2] for run in runs] == [
        ("dbt", "run"),
        ("dbt", "seed"),
        ("dbt", "build"),
        ("python", "step_weather_squares.py"),
    ] + [("dbt", "build")] * 2


@pytest.mark.parametrize("lane", [None, "monthly", "hourly"])
def test_the_writers_build_is_never_split_and_never_names_the_tag(lane):
    split = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane)
    whole = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, manifest=NONE_ALONE)

    writers = [run for run in split if "writers" in run.label]
    assert [run.argv for run in writers] == [_writers(whole).argv] and _writers(split) == _writers(whole)
    assert split[-1] == whole[-1], "and so is the data-quality pass after them"
    assert not any(build_marts.BUILDS_ALONE in argument for argument in _writers(whole).argv)


def _alone_manifest(edges: dict[str, list[str]], tagged: tuple[str, ...] = (), hourly: tuple[str, ...] = ()) -> dict:
    """A manifest of these parent -> children edges over ids like `model.ourhike.heavy` and
    `source.ourhike.derived.dem_samples`, every derived source STEPS writes among them: the `tagged` names carry
    builds_alone, a pub_ model sits under models/publish, and the `hourly` sources are hourly (the others monthly)."""
    edges = {**{f"source.ourhike.derived.{table}": [] for table in STEP_TABLES}, **edges}
    ids = set(edges) | {child for children in edges.values() for child in children}
    nodes, sources, parents = {}, {}, {uid: [] for uid in ids}
    for parent, children in edges.items():
        for child in children:
            parents[child].append(parent)
    for uid in ids:
        kind, _, name = uid.split(".", 2)
        if kind == "source":
            source_name, table = name.split(".")
            cadence = "hourly" if uid in hourly else "monthly"
            sources[uid] = {"source_name": source_name, "name": table, "config": {"meta": {"cadence": cadence}}}
            continue
        folder = "publish" if name.startswith("pub_") else "intermediate"
        nodes[uid] = {
            "resource_type": kind,
            "package_name": "ourhike",
            "original_file_path": f"models/{folder}/{name}.sql",
            "config": {"tags": ["builds_alone"] if name in tagged else []},
        }
    return {"nodes": nodes, "sources": sources, "child_map": {uid: edges.get(uid, []) for uid in ids}, "parent_map": parents}


#: derived.dem_samples -> stg -> heavy (tagged) -> below -> pub_below, with stg -> beside and a test on heavy: what
#: step_dem_sampling unblocks holds a model that builds alone, one beside it and one it feeds.
HEAVY = _alone_manifest(
    {
        "source.ourhike.derived.dem_samples": ["model.ourhike.stg"],
        "model.ourhike.stg": ["model.ourhike.heavy", "model.ourhike.beside"],
        "model.ourhike.heavy": ["model.ourhike.below", "test.ourhike.unique_heavy_id"],
        "model.ourhike.below": ["model.ourhike.pub_below"],
    },
    tagged=("heavy",),
)


def test_given_the_manifest_a_build_with_no_tagged_model_in_its_selection_is_not_split():
    """Stage A excludes source:derived+, which holds heavy, so it runs whole; what dem_samples unblocks runs in three."""
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True, manifest=HEAVY)
    whole = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True, manifest=NONE_ALONE)

    assert [run.label for run in runs] == [
        build_marts.ELEMENTARY_TABLES,
        build_marts.SEED,
        "stage A: everything no Python step reads back",
        "step_dem_sampling",
        "what derived.dem_samples unblocks: all but the models that build alone and what they feed",
        "what derived.dem_samples unblocks: the models that build alone, one at a time",
        "what derived.dem_samples unblocks: what the models that build alone feed",
        "the pub_ writers",
        build_marts.ELEMENTARY_CHECKS,
        build_marts.DATA_QUALITY_LABEL,
    ]
    assert runs[2] == whole[2]


def test_given_the_manifest_a_pass_that_selects_nothing_is_left_out():
    """heavy feeds only its writer and its own test, so after the models that build alone there is nothing to build."""
    leaf = _alone_manifest(
        {
            "source.ourhike.derived.dem_samples": ["model.ourhike.stg"],
            "model.ourhike.stg": ["model.ourhike.heavy"],
            "model.ourhike.heavy": ["model.ourhike.pub_heavy", "test.ourhike.unique_heavy_id"],
        },
        tagged=("heavy",),
    )

    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True, manifest=leaf)

    assert [run.label for run in runs if run.label.startswith("what")] == [
        "what derived.dem_samples unblocks: all but the models that build alone and what they feed",
        "what derived.dem_samples unblocks: the models that build alone, one at a time",
    ]


def test_selects_anything_reads_a_selector_it_does_not_know_as_everything_selected_and_nothing_excluded():
    assert build_marts.selects_anything(HEAVY, ("heavy",), ())
    assert build_marts.selects_anything(HEAVY, (ALONE,), ("heavy", "1+tag:builds_alone"))
    assert not build_marts.selects_anything(HEAVY, (ALONE,), ("source:derived+",))
    assert not build_marts.selects_anything(NONE_ALONE, (ALONE,), ())


def test_main_runs_the_split_passes_the_manifest_leaves_in_and_says_which_models_build_alone(monkeypatch, tmp_path, capsys):
    code, recorder = _main(monkeypatch, tmp_path, HEAVY)

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    assert code == 0
    assert [(argv, cwd) for argv, cwd, _ in recorder.calls] == argvs(
        plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True, history=_history(tmp_path), manifest=HEAVY)
    )
    alone = [argv for argv, _, _ in recorder.calls if "--threads" in argv]
    assert [argv[argv.index("-s") + 1] for argv in alone] == [
        "source:derived.dem_samples+,tag:builds_alone",
        "path:models/publish",  # the writers, one at a time too
        NO_CHECKS,  # and Elementary's checks
    ]
    assert "-- build_marts: 1 model(s) build alone (heavy)" in capsys.readouterr().out


def test_alone_problems_passes_a_tagged_model_that_reads_only_untagged_parents_or_another_tagged_one():
    chained = _alone_manifest(
        {
            "model.ourhike.stg": ["model.ourhike.heavy", "model.ourhike.beside"],
            "model.ourhike.heavy": ["model.ourhike.heavier", "model.ourhike.below"],
            "model.ourhike.heavier": ["model.ourhike.below_heavier"],
        },
        tagged=("heavy", "heavier"),
    )

    assert build_marts.alone_problems(HEAVY) == []
    assert build_marts.alone_problems(chained) == []


def test_alone_problems_refuses_a_tagged_model_reading_what_another_tagged_model_feeds():
    """Pass (b) would build heavier before pass (c) builds below, which heavier reads."""
    bad = _alone_manifest(
        {
            "model.ourhike.heavy": ["model.ourhike.below"],
            "model.ourhike.below": ["model.ourhike.middle"],
            "model.ourhike.middle": ["model.ourhike.heavier"],
        },
        tagged=("heavy", "heavier"),
    )

    problems = build_marts.alone_problems(bad)

    assert [problem.split(":")[0] for problem in problems] == [
        "heavier builds alone (builds_alone) and reads below, which is downstream of heavy",
        "heavier builds alone (builds_alone) and reads middle, which is downstream of heavy",
    ]
    assert problems[0].endswith("Tag every model between them builds_alone too, or untag one end")


def test_alone_problems_refuses_a_test_of_a_tagged_model_that_reads_what_the_tagged_model_feeds():
    """Eager selection runs the test in pass (b), beside heavy, before pass (c) has built below."""
    bad = _alone_manifest(
        {
            "model.ourhike.heavy": ["model.ourhike.below", "test.ourhike.relationships_heavy_below"],
            "model.ourhike.below": ["test.ourhike.relationships_heavy_below"],
        },
        tagged=("heavy",),
    )

    assert build_marts.alone_problems(bad) == [
        "test.ourhike.relationships_heavy_below tests heavy, which builds alone (builds_alone), and reads below, which "
        "is downstream of heavy: it would run before that is built"
    ]


def test_alone_problems_refuses_a_tagged_model_an_hourly_source_reaches_since_the_hourly_lane_never_splits():
    """No hourly-cadence model may carry the tag: the hourly lane would build it beside the rest. Every build_marts.py
    run checks the real project's manifest this way after `dbt seed`, CI's fixture build among them."""
    hourly = _alone_manifest(
        {"source.ourhike.ourhike.raw_ourhike__closures": ["model.ourhike.int_closures__unioned"]},
        tagged=("int_closures__unioned",),
        hourly=("source.ourhike.ourhike.raw_ourhike__closures",),
    )

    assert build_marts.alone_problems(hourly) == [
        "int_closures__unioned builds alone (builds_alone), and an hourly or daily source reaches it: the hourly lane "
        "never splits its builds (each split is one more dbt invocation inside its step cap), so it would build "
        "beside other models there"
    ]


def test_main_refuses_after_the_seeds_when_the_split_would_build_a_tagged_model_before_its_input(monkeypatch, tmp_path, capsys):
    bad = _alone_manifest(
        {"model.ourhike.heavy": ["model.ourhike.below"], "model.ourhike.below": ["model.ourhike.heavier"]},
        tagged=("heavy", "heavier"),
    )

    code, recorder = _main(monkeypatch, tmp_path, bad)

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ELEMENTARY, ("dbt", "seed")]
    assert "heavier builds alone (builds_alone) and reads below" in capsys.readouterr().out


@pytest.mark.parametrize(
    "model", ["intermediate/places/int_places__resolved.sql", "intermediate/trail_network/int_trail_network__cuts.sql"]
)
def test_the_two_models_monthly_run_20_ran_out_of_memory_on_carry_the_tag_in_their_own_config(model):
    first, second = (DBT_DIR / "models" / model).read_text().splitlines()[:2]

    assert re.fullmatch(r"\{\{ config\(.*tags=\['builds_alone'\].*\) \}\}", first), first
    assert second.startswith("-- builds_alone:") and "37296900535" in second, "the comment names run 20"


# --- The row history (build_marts.py's docstring, "THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST") ---


def test_plan_with_a_history_store_restores_before_the_seeds_and_saves_after_the_writers_and_the_checks():
    history = History("s3://bucket/history/monthly", False, "/venv/extract/bin/python")
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, history=history)

    store = ("--url", "s3://bucket/history/monthly", "--warehouse", "/w/warehouse.duckdb")
    assert runs[0].argv == ("/venv/extract/bin/python", "row_history.py", "restore", *store)
    assert (runs[1].argv, runs[1].cwd) == ELEMENTARY_RUN and runs[2].argv[:2] == ("dbt", "seed")
    assert runs[-1].argv == ("/venv/extract/bin/python", "row_history.py", "save", *store, "--keep-days", "430")
    stages = [run.stage for run in runs[-4:-1]]
    assert stages == [build_marts.WRITERS, build_marts.CHECKS, build_marts.DATA_QUALITY], "the save waits for all three"


def test_no_history_save_restores_and_builds_with_the_history_and_saves_nothing(monkeypatch, tmp_path, capsys):
    """publish-conditions.yml's hourly build when the notices legs' newest served copy was not read: a notice
    missing from that build must never be closed in the history, so the save is left out and nothing else moves."""
    history = History("s3://bucket/history/conditions_ua", False, "python")
    saved = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, history=history)
    unsaved = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, history=history, save_history=False)

    assert argvs(unsaved) == argvs(saved)[:-1] and saved[-1].label == build_marts.SAVE_LABEL

    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), extra=("--no-history-save",))

    assert code == 0
    assert [argv[2] for argv, _, _ in recorder.calls if argv[:2] == RESTORE] == ["restore"]
    assert "::warning title=Row history not saved::" in capsys.readouterr().out


def test_a_cold_start_reaches_the_restore_as_its_flag():
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=True, history=History("/h", True, "python"))

    assert runs[0].argv[-1] == "--cold-start"


def test_no_history_store_outside_the_fixtures_is_refused_before_anything_runs(monkeypatch, tmp_path):
    monkeypatch.delenv("OURHIKE_HISTORY_URL", raising=False)
    with pytest.raises(ValueError, match="no row-history store"):
        build_marts.resolve_history(None, fixtures=False, cold_start=False, python="python", started={})
    with pytest.raises(SystemExit):
        build_marts.main(["--lane", "monthly", "--warehouse", str(tmp_path / "w.duckdb"), "--dry-run"])


def test_the_fixtures_with_no_store_named_cold_start_in_a_new_temporary_directory():
    history, notice = build_marts.resolve_history(None, fixtures=True, cold_start=False, python="python", started={})

    assert history.cold_start and Path(history.url).is_dir() and not any(Path(history.url).iterdir())
    assert "no later run reads" in notice


def test_a_store_listed_as_started_may_not_cold_start_and_one_not_listed_may_with_a_warning():
    started = {"monthly": "refresh-reference.yml run 1"}
    lists = {"started": started, "elementary_started": started}

    listed, quiet = build_marts.resolve_history(
        "s3://b/history/monthly", fixtures=False, cold_start=False, python="python", **lists
    )
    unlisted, warning = build_marts.resolve_history(
        "s3://b/history/conditions_ua", fixtures=False, cold_start=False, python="python", **lists
    )
    forced, _ = build_marts.resolve_history("s3://b/history/monthly", fixtures=False, cold_start=True, python="python", **lists)

    assert not listed.cold_start and not listed.elementary_cold_start and quiet is None
    assert unlisted.cold_start and warning.startswith("::warning") and "conditions_ua" in warning
    assert unlisted.elementary_cold_start, "a store whose row history may start may start Elementary's"
    assert forced.cold_start and forced.elementary_cold_start


def test_a_store_started_before_decision_102_may_start_elementarys_history_until_it_is_listed_for_it():
    """Every store saved before Elementary came holds the snapshots and no elementary.json (row_history.py's
    docstring, "THE COLD START"): its first run with Elementary starts that history, said in a warning, and only a
    store [elementary_started] lists refuses a missing one."""
    started = {"monthly": "refresh-reference.yml run 1"}

    first, warning = build_marts.resolve_history(
        "s3://b/history/monthly", fixtures=False, cold_start=False, python="python", started=started, elementary_started={}
    )
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, history=first)

    assert not first.cold_start and first.elementary_cold_start
    assert warning.startswith("::warning title=Elementary's history not started::") and "[elementary_started]" in warning
    assert runs[0].argv[-1] == "--elementary-cold-start", "the snapshots' history may not start again, Elementary's may"


def test_row_history_stores_toml_lists_elementary_stores_only_among_the_started_ones():
    """A store's Elementary history is saved by the same save as its snapshots, so a store listed for Elementary and not
    for the snapshots is a mistake in the file: its --cold-start would let Elementary's history start again."""
    elementary = build_marts.started_elementary_stores()

    assert set(elementary) <= set(build_marts.started_history_stores())
    assert all("/" not in name and isinstance(run, str) and run for name, run in elementary.items())


@pytest.mark.parametrize(("lane", "days"), [("monthly", "430"), ("hourly", "21"), (None, "430")])
def test_the_save_keeps_its_lanes_days_of_elementarys_history(lane, days):
    history = History("s3://bucket/history/x", False, "python")
    save = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, history=history)[-1]

    assert save.label == build_marts.SAVE_LABEL
    assert save.argv[save.argv.index("--keep-days") + 1] == days


def test_degrade_reaches_both_the_restore_and_the_save_as_elementarys_policy():
    history = History("s3://bucket/history/conditions_ua", False, "python", on_failure="degrade")
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", history=history)

    for run in (runs[0], runs[-1]):
        assert run.argv[-2:] == ("--elementary-on-failure", "degrade"), run.label
    plain = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, history=History("/h", False, "python"))
    assert not [run for run in plain if "--elementary-on-failure" in run.argv]


@pytest.mark.parametrize("which", [1, -1], ids=["restore", "save"])
def test_elementarys_history_alone_failing_under_degrade_publishes_with_the_row_dates_and_goes_red(monkeypatch, tmp_path, which):
    """row_history.py's exit 3 (its docstring, "ITS FAILURES ARE THE ROW HISTORY'S"): the row history was restored or
    saved and Elementary's was not, so the build carries on with the snapshots and answers PARTIAL_EXIT, never
    DEGRADED_EXIT, whose workflow message says the row dates were nulled."""
    manifest = _manifest(*STEP_TABLES)
    calls = len(_main(monkeypatch, tmp_path, manifest)[1].calls)
    position = 1 if which == 1 else calls

    code, recorder = _main(
        monkeypatch,
        tmp_path,
        manifest,
        codes={position: build_marts.ELEMENTARY_DEGRADED_EXIT},
        extra=("--history-on-failure", "degrade"),
    )

    assert code == build_marts.PARTIAL_EXIT
    assert len(recorder.calls) == calls, "every command still runs, the save included"
    assert all(env.get("OURHIKE_ROW_HISTORY") != "off" for _, _, env in recorder.calls), "the snapshots stay in"
    assert not [argv for argv, _, _ in recorder.calls[1:] if build_marts.SNAPSHOTS in argv]


def test_row_history_exit_3_without_degrade_is_a_plain_failure(monkeypatch, tmp_path):
    """Only --elementary-on-failure degrade makes row_history.py answer 3; under `fail` any exit of the restore stops."""
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={1: build_marts.ELEMENTARY_DEGRADED_EXIT})

    assert code == build_marts.ELEMENTARY_DEGRADED_EXIT and len(recorder.calls) == 1


def test_row_history_stores_toml_lists_store_names_with_the_run_that_started_each():
    started = build_marts.started_history_stores()

    assert all("/" not in name and isinstance(run, str) and run for name, run in started.items())


def test_a_failed_restore_stops_the_build_before_dbt_by_default(monkeypatch, tmp_path):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={1: 1})

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE]


def test_a_degraded_build_runs_every_dbt_command_without_snapshots_or_history_and_saves_nothing(monkeypatch, tmp_path):
    """The conditions legs (--history-on-failure degrade): publish with null dates, save nothing, exit DEGRADED_EXIT."""
    manifest = _manifest(*STEP_TABLES)
    code, recorder = _main(monkeypatch, tmp_path, manifest, codes={1: 2}, extra=("--history-on-failure", "degrade"))

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    after_restore = [(argv, cwd) for argv, cwd, _ in recorder.calls][1:]
    assert code == build_marts.DEGRADED_EXIT
    assert after_restore == argvs(
        plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True, snapshots=False, manifest=manifest)
    )
    assert not [argv for argv, _, _ in recorder.calls if argv[2:3] == ("save",)], "a degraded build never saves"
    builds = [argv for argv, _, _ in recorder.calls if argv[:2] == ("dbt", "build")]
    writers = [argv for argv in builds if "-s" in argv and argv[argv.index("-s") + 1] == "path:models/publish"]
    assert len(writers) == 1 and all(build_marts.SNAPSHOTS in argv for argv in builds if argv not in writers)
    for _, _, env in recorder.calls[1:]:
        assert env["OURHIKE_ROW_HISTORY"] == "off", "macros/row_history.sql's row_history_mart() reads it"


def test_a_command_that_fails_with_the_degraded_exit_code_is_answered_as_a_plain_failure(monkeypatch, tmp_path):
    """publish-conditions.yml publishes on DEGRADED_EXIT, so only a build that did degrade may answer with it."""
    for extra in ((), ("--history-on-failure", "degrade")):
        code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={4: build_marts.DEGRADED_EXIT}, extra=extra)

        assert code == 1


def test_without_snapshots_every_build_but_the_writers_excludes_them():
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True, snapshots=False)

    builds = [run.argv for run in runs if run.argv[:2] == ("dbt", "build")]
    assert len(builds) == 8, "stage A and the step's build, each split in three, the writers, and the data-quality file"
    assert [build_marts.SNAPSHOTS in argv for argv in builds] == [True] * 6 + [False, True]


def test_built_by_names_the_commit_and_the_workflow_run_in_characters_a_sql_literal_takes():
    environ = {"GITHUB_SHA": "0123456789abcdef0123", "GITHUB_RUN_ID": "37109384156", "GITHUB_RUN_ATTEMPT": "2"}

    assert build_marts.built_by(environ) == "0123456789ab run 37109384156.2"
    assert build_marts.built_by({"OURHIKE_BUILT_BY": "x'; drop table t; --"}) == "x drop table t --"


def _results(path, *results):
    path.write_text(json.dumps({"results": list(results)}), encoding="utf-8")
    return path


def test_a_failed_tests_rows_are_asked_again_cut_short_and_printed_in_a_group(tmp_path):
    """Soak run 525 (publish-conditions.yml 37216623795) failed three tests on live club notices and printed no row."""
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema intermediate")
        con.execute("create table intermediate.leaks as select range as n, repeat('x', 500) as words from range(25)")
    sql = 'select * from "warehouse"."intermediate"."leaks" where n >= 0;'
    results = _results(
        tmp_path / "run_results.json",
        {"unique_id": "test.ourhike.a_leak", "status": "fail", "failures": 25, "compiled_code": sql},
        {"unique_id": "test.ourhike.fine", "status": "pass", "failures": 0, "compiled_code": sql},
        {"unique_id": "model.ourhike.m", "status": "error", "compiled_code": sql},
    )

    lines = build_marts.failed_test_rows(warehouse, since=0.0, results_path=results)

    assert lines[0] == "::group::test.ourhike.a_leak: 25 row(s), fail" and lines[-1] == "::endgroup::"
    rows = [json.loads(line) for line in lines[1:-1]]
    assert len(rows) == build_marts.FAILED_ROWS_SHOWN
    assert {len(row["words"]) for row in rows} == {build_marts.FAILED_VALUE_WIDTH}


def test_an_earlier_stages_run_results_say_nothing_about_this_failure(tmp_path):
    results = _results(
        tmp_path / "run_results.json", {"unique_id": "test.ourhike.a", "status": "fail", "compiled_code": "select 1"}
    )
    assert build_marts.failed_test_rows(tmp_path / "w.duckdb", since=results.stat().st_mtime + 60, results_path=results) == []


def test_a_test_whose_sql_cannot_be_asked_again_says_why(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    duckdb.connect(str(warehouse)).close()
    results = _results(
        tmp_path / "run_results.json",
        {"unique_id": "test.ourhike.gone", "status": "error", "failures": None, "compiled_code": "select * from nowhere"},
    )
    lines = build_marts.failed_test_rows(warehouse, since=0.0, results_path=results)
    assert lines[0].startswith("::group::test.ourhike.gone") and lines[1].startswith("(not asked again: ")


def test_an_expression_tests_failure_shows_the_models_own_failing_rows_not_its_constant(tmp_path):
    """Soak run 526 (publish-conditions.yml 37217363236) printed {"1": "1"} for int_warnings__wording_leaks' test."""
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema intermediate")
        con.execute("create table intermediate.leaks as select 'club_x' as source_key, 'title' as column_name")
    uid = "test.ourhike.dbt_utils_expression_is_true_leaks_false.1"
    results = _results(
        tmp_path / "run_results.json", {"unique_id": uid, "status": "fail", "failures": 1, "compiled_code": "select 1"}
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "nodes": {
                    uid: {
                        "attached_node": "model.ourhike.leaks",
                        "test_metadata": {"name": "expression_is_true", "kwargs": {"expression": "false"}},
                        "config": {"where": None},
                    },
                    "model.ourhike.leaks": {"relation_name": '"warehouse"."intermediate"."leaks"'},
                }
            }
        )
    )

    lines = build_marts.failed_test_rows(warehouse, since=0.0, results_path=results, manifest_path=manifest)

    assert json.loads(lines[1]) == {"source_key": "club_x", "column_name": "title"}


# --- Decision 81: one source or one writer never stops the rest ---------------------------------------------------


def _is_writers_run(argv: tuple[str, ...]) -> bool:
    return "-s" in argv and argv[argv.index("-s") + 1] == "path:models/publish"


def _is_stage_a(argv: tuple[str, ...]) -> bool:
    return argv[:2] == ("dbt", "build") and "-s" not in argv


class _DbtRuns(_Recorder):
    """_Recorder whose dbt runs each leave run results, and files, as a real dbt run would before it exits. Each answer
    is (which run, exit code, results, files to write) and answers the first call it matches, once."""

    def __init__(self, results_path: Path, answers: list[tuple]):
        super().__init__()
        self.results_path = results_path
        self.answers = list(answers)

    def __call__(self, argv, *, cwd, env, check):
        self.calls.append((tuple(argv), cwd, env))
        for index, (matches, code, results, files) in enumerate(self.answers):
            if matches(tuple(argv)):
                del self.answers[index]
                for path, text in files.items():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
                _results(self.results_path, *results)
                return subprocess.CompletedProcess(argv, code)
        return subprocess.CompletedProcess(argv, 0)


WRITER_LOCATIONS = {
    "model.ourhike.pub_conditions_closures": "conditions_closures.json",
    "model.ourhike.pub_conditions_notices": "conditions_notices.json",
    "model.ourhike.pub_conditions_reports": "conditions_reports.json",
}
REPORTS_TEST = "test.ourhike.not_null_pub_conditions_reports_generated_at.1"
NOTICES_TEST = "test.ourhike.not_null_pub_conditions_notices_generated_at.1"


def _conditions_writers_manifest(tmp_path: Path) -> dict:
    """Three conditions writers and a test of one, in a fixture manifest; and the warehouse failed_test_rows() asks."""
    duckdb.connect(str(tmp_path / "warehouse.duckdb")).close()
    manifest = _manifest(*STEP_TABLES)
    manifest["nodes"] = {writer: {"config": {"location": location}} for writer, location in WRITER_LOCATIONS.items()}
    for test, writer in (
        (REPORTS_TEST, "model.ourhike.pub_conditions_reports"),
        (NOTICES_TEST, "model.ourhike.pub_conditions_notices"),
    ):
        manifest["nodes"][test] = {"depends_on": {"nodes": [writer]}, "attached_node": writer}
    return manifest


def test_a_writer_that_fails_while_the_others_write_leaves_no_file_and_the_build_exits_partial_naming_what_wrote(
    monkeypatch, tmp_path, capsys
):
    """Soak run 531 (publish-conditions.yml 37237506320): pub_conditions_notices failed on one Idaho polygon after six
    writers had written, and nothing published. Now the failed writer's file, half-written here, is removed, and so is
    the file of a writer whose own test failed, so neither can publish; the file that wrote stays, the log names it,
    the row history is still saved, and the build answers PARTIAL_EXIT for the workflow to publish and then go red."""
    processed = tmp_path / "processed"
    files = {
        processed / "conditions_closures.json": '{"closures": []}',
        processed / "conditions_notices.json": '{"generated_at": "2026-10',
        processed / "conditions_reports.json": '{"reports": [null]}',
    }
    results = [
        {"unique_id": "model.ourhike.pub_conditions_closures", "status": "success"},
        {"unique_id": "model.ourhike.pub_conditions_notices", "status": "error", "message": "TopologyException"},
        {"unique_id": "model.ourhike.pub_conditions_reports", "status": "success"},
        {"unique_id": REPORTS_TEST, "status": "fail", "failures": 1},
        # Skipped because its writer failed, so it names nothing the writer's own error does not.
        {"unique_id": NOTICES_TEST, "status": "skipped"},
    ]
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_writers_run, 1, results, files)])

    code, _ = _main(monkeypatch, tmp_path, _conditions_writers_manifest(tmp_path), recorder=recorder)

    out = capsys.readouterr().out
    assert code == build_marts.PARTIAL_EXIT
    assert sorted(path.name for path in processed.iterdir()) == ["conditions_closures.json"]
    assert "-- build_marts: wrote 1 file(s): conditions_closures.json" in out
    assert "::error title=pub_conditions_notices failed::its model finished error, so conditions_notices.json is removed" in out
    assert f"::error title=pub_conditions_reports failed::{REPORTS_TEST} finished fail" in out
    assert recorder.calls[-1][0][:3] == (*RESTORE, "save"), "the marts passed, so the row history is saved"


def test_a_failure_in_the_writers_run_that_is_no_writers_own_still_stops_the_build(monkeypatch, tmp_path):
    results = [
        {"unique_id": "model.ourhike.pub_conditions_closures", "status": "error"},
        {"unique_id": "model.ourhike.int_closures__gate", "status": "error"},
    ]
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_writers_run, 1, results, {})])

    code, _ = _main(monkeypatch, tmp_path, _conditions_writers_manifest(tmp_path), recorder=recorder)

    assert code == 1
    assert not [argv for argv, _, _ in recorder.calls if argv[2:3] == ("save",)]


def test_a_test_that_holds_a_source_warned_so_the_build_names_its_rows_publishes_and_exits_partial(monkeypatch, tmp_path, capsys):
    """Soak runs 525 to 527 and 530 failed every hourly file on the wording-leak and region tests. At warn, with
    `holds_a_source`, the gate has held the source, the build goes on, the rows are printed as a failed test's are,
    and the build answers PARTIAL_EXIT."""
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema intermediate")
        con.execute("create table intermediate.leaks as select 'club_x' as source_key, 'club_x:2' as row_id")
    leak = "test.ourhike.dbt_utils_expression_is_true_int_warnings__wording_leaks_false.1"
    quiet = "test.ourhike.dbt_utils_expression_is_true_int_closures__gate_passed.1"
    manifest = _manifest(*STEP_TABLES)
    manifest["nodes"] = {
        leak: {
            "config": {"meta": {build_marts.HOLDS_A_SOURCE: True}},
            "attached_node": "model.ourhike.leaks",
            "test_metadata": {"name": "expression_is_true", "kwargs": {"expression": "false"}},
        },
        quiet: {"config": {"meta": {}}},
        "model.ourhike.leaks": {"relation_name": '"warehouse"."intermediate"."leaks"'},
    }
    results = [
        {"unique_id": leak, "status": "warn", "failures": 1, "compiled_code": "select 1"},
        {"unique_id": quiet, "status": "warn", "failures": 4, "compiled_code": "select 1"},
    ]
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_stage_a, 0, results, {})])

    code, _ = _main(monkeypatch, tmp_path, manifest, recorder=recorder)

    out = capsys.readouterr().out
    assert code == build_marts.PARTIAL_EXIT
    assert f"::group::{leak}: 1 row(s), warn" in out and '{"source_key": "club_x", "row_id": "club_x:2"}' in out
    assert quiet not in out, "a warning that holds no source is the gate's own, and stays a warning"
    assert recorder.calls[-1][0][:3] == (*RESTORE, "save")


def _one_source_setup(tmp_path: Path, monkeypatch) -> tuple[dict, Path]:
    readers = tmp_path / "notice_readers.csv"
    readers.write_text(
        "source_key,club,notice_type,reader,listing,raw_table,staged_by,steward_kind\n"
        "club_x,a,closures,arcgis_layer,full,raw_a__club_x,stg_a__club_x,club\n"
        "club_y,a,warnings,page_notice,full,raw_a__club_y,stg_a__club_y,club\n"
        "nynjtc_trail_alerts,nynjtc,closures,wordpress_posts,full,raw_nynjtc__nynjtc_trail_alerts,hand,club\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_marts, "NOTICE_READERS", readers)
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema raw")
        for table in ("raw_a__club_x", "raw_a__club_y", "raw_nynjtc__nynjtc_trail_alerts"):
            con.execute(f"create table raw.{table} as select 1 as objectid")
    manifest = _manifest(*STEP_TABLES)
    for club, table in (("a", "raw_a__club_x"), ("a", "raw_a__club_y"), ("nynjtc", "raw_nynjtc__nynjtc_trail_alerts")):
        manifest["sources"][f"source.ourhike.{club}.{table}"] = {"name": table, "identifier": table, "source_name": club}
    manifest["parent_map"] = {
        "model.ourhike.base_a__club_x": ["source.ourhike.a.raw_a__club_x", "seed.ourhike.notice_status_values"],
        "model.ourhike.stg_a__club_x": ["model.ourhike.base_a__club_x"],
        "model.ourhike.stg_a__club_y": ["source.ourhike.a.raw_a__club_y"],
        "model.ourhike.base_nynjtc__nynjtc_trail_alerts": ["source.ourhike.nynjtc.raw_nynjtc__nynjtc_trail_alerts"],
        "model.ourhike.int_closures__club_notices_part_1_unioned": ["model.ourhike.stg_a__club_x", "model.ourhike.stg_a__club_y"],
        "seed.ourhike.notice_status_values": [],
    }
    return manifest, warehouse


def _raw_tables(warehouse: Path) -> list[str]:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        return sorted(
            name
            for (name,) in con.execute("select table_name from information_schema.tables where table_schema = 'raw'").fetchall()
        )


def test_a_model_of_one_club_notice_source_failing_drops_its_raw_tables_and_runs_stage_a_once_more(monkeypatch, tmp_path, capsys):
    """A SQL error in one source's own staging model used to skip every union, mart and writer. Its raw table is
    dropped instead, so the second stage A holds that source as not in this warehouse (int_closures__gate), and the
    build goes on to answer PARTIAL_EXIT."""
    manifest, warehouse = _one_source_setup(tmp_path, monkeypatch)
    failed = [
        {"unique_id": "model.ourhike.stg_a__club_x", "status": "error", "message": "Conversion Error"},
        {"unique_id": "model.ourhike.int_closures__club_notices_part_1_unioned", "status": "skipped"},
    ]
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_stage_a, 1, failed, {}), (_is_stage_a, 0, [], {})])

    code, _ = _main(monkeypatch, tmp_path, manifest, recorder=recorder)

    assert code == build_marts.PARTIAL_EXIT
    assert _raw_tables(warehouse) == ["raw_a__club_y", "raw_nynjtc__nynjtc_trail_alerts"]
    stage_a = [argv for argv, _, _ in recorder.calls if _is_stage_a(argv)]
    assert len(stage_a) == 2 and stage_a[0] == stage_a[1]
    assert "::error title=club_x held for a failed model::" in capsys.readouterr().out
    assert recorder.calls[-1][0][:3] == (*RESTORE, "save")


@pytest.mark.parametrize(
    ("failed_node", "why"),
    [
        ("model.ourhike.int_closures__club_notices_part_1_unioned", "a union of two sources"),
        ("model.ourhike.base_nynjtc__nynjtc_trail_alerts", "a hand-staged source, whose base reads no absent table"),
        ("model.ourhike.int_closures__gate", "a model of no one source"),
    ],
)
def test_a_failed_model_that_is_not_one_generated_sources_own_still_stops_the_build(monkeypatch, tmp_path, failed_node, why):
    manifest, warehouse = _one_source_setup(tmp_path, monkeypatch)
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_stage_a, 1, [{"unique_id": failed_node, "status": "error"}], {})])

    code, _ = _main(monkeypatch, tmp_path, manifest, recorder=recorder)

    assert code == 1, why
    assert len(_raw_tables(warehouse)) == 3, "nothing is dropped"
    assert len([argv for argv, _, _ in recorder.calls if _is_stage_a(argv)]) == 1


def test_a_second_failure_of_stage_a_after_the_drop_stops_the_build(monkeypatch, tmp_path):
    manifest, _ = _one_source_setup(tmp_path, monkeypatch)
    failed = [{"unique_id": "model.ourhike.stg_a__club_x", "status": "error"}]
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_stage_a, 1, failed, {}), (_is_stage_a, 1, failed, {})])

    code, _ = _main(monkeypatch, tmp_path, manifest, recorder=recorder)

    assert code == 1
    assert len([argv for argv, _, _ in recorder.calls if _is_stage_a(argv)]) == 2, "stage A runs once more, not again"


def _withdrawn_warehouse(tmp_path: Path, notes: tuple[str, ...] = ("loaded", "unavailable"), notes_present: bool = False) -> Path:
    """The warehouse a conditions leg leaves when the reader cannot see public.field_notes: raw_ourhike__closures
    loaded; raw_ourhike__notes and raw_ourhike__disputes withdrawn (extract/_warehouse.py's committed_tables()), so
    neither table is there, and `_extract_runs` holding each run's outcome for them, oldest first."""
    warehouse = tmp_path / "warehouse.duckdb"
    rows = [("run-1", "raw_ourhike__closures", "loaded"), ("run-2", "raw_ourhike__closures", "loaded")]
    rows += [(f"run-{n}", "raw_ourhike__notes", outcome) for n, outcome in enumerate(notes, 1)]
    rows += [("run-1", "raw_ourhike__disputes", "loaded"), ("run-2", "raw_ourhike__disputes", "unavailable")]
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema raw")
        con.execute("create table raw.raw_ourhike__closures as select 'c1' as id")
        if notes_present:
            con.execute("create table raw.raw_ourhike__notes as select 'n1' as id")
        con.execute("create table raw._extract_runs (run_id varchar, table_name varchar, outcome varchar)")
        con.executemany("insert into raw._extract_runs values (?, ?, ?)", rows)
    return warehouse


class _DbtLackingTables(_DbtRuns):
    """dbt as it answered PY-2's warehouse (dbt 2.0.6, 2026-10-06: "Catalog Error: Table with name raw_ourhike__notes
    does not exist!", review finding PY-2 of PR #1805 — dlt → dbt re-platform as one go/no-go change): stage A fails on
    each base model whose raw table the warehouse lacks, unless the build excludes that table's source and everything
    below it."""

    BASES = {"raw_ourhike__notes": "base_ourhike__notes", "raw_ourhike__disputes": "base_ourhike__disputes"}

    def __init__(self, results_path: Path, warehouse: Path):
        super().__init__(results_path, [])
        self.missing = [table for table in self.BASES if table not in _raw_tables(warehouse)]

    def __call__(self, argv, *, cwd, env, check):
        argv = tuple(argv)
        failing = [table for table in self.missing if f"source:ourhike.{table}+" not in argv]
        if _is_stage_a(argv) and failing:
            self.calls.append((argv, cwd, env))
            errors = [{"unique_id": f"model.ourhike.{self.BASES[table]}", "status": "error"} for table in failing]
            _results(self.results_path, *errors)
            return subprocess.CompletedProcess(argv, 1)
        return super().__call__(argv, cwd=cwd, env=env, check=check)


def test_notes_and_disputes_the_extract_withdrew_are_left_out_of_every_dbt_build_and_the_rest_publishes(
    monkeypatch, tmp_path, capsys
):
    """#922 — The whole conditions bake has been failing hourly since field notes landed, so the closures baseline is
    ageing, back on the dbt path (review finding PY-2 of PR #1805): with public.field_notes unreadable, the extract
    withdraws notes and disputes by design and closures carry on, and stage A then failed on base_ourhike__notes, so no
    closures, warnings or notices file was written. Now each withdrawn table's source, and everything below it, is left
    out of every dbt build, the writers run, and the build answers PARTIAL_EXIT so the workflow publishes and goes red."""
    warehouse = _withdrawn_warehouse(tmp_path)
    recorder = _DbtLackingTables(tmp_path / "run_results.json", warehouse)

    code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), recorder=recorder)

    builds = [argv for argv, _, _ in recorder.calls if argv[:2] == ("dbt", "build")]
    assert code == build_marts.PARTIAL_EXIT
    assert any(_is_writers_run(argv) for argv in builds), "the writers ran"
    for argv in builds:
        tail = argv[argv.index("--exclude") :]
        assert "source:ourhike.raw_ourhike__notes+" in tail and "source:ourhike.raw_ourhike__disputes+" in tail, argv
    out = capsys.readouterr().out
    assert "::error title=raw_ourhike__notes withdrawn::" in out and "::error title=raw_ourhike__disputes withdrawn::" in out
    assert recorder.calls[-1][0][:3] == (*RESTORE, "save"), "no mart reads either table, so the history is saved"


@pytest.mark.parametrize(
    ("notes", "notes_present", "why"),
    [
        (("loaded", "incomplete"), False, "absent without a withdrawal: a missing table is not evidence of anything"),
        (("unavailable", "loaded"), True, "withdrawn once and loaded since, so it is in this warehouse"),
    ],
)
def test_notes_the_run_log_does_not_say_are_withdrawn_now_are_never_left_out(monkeypatch, tmp_path, notes, notes_present, why):
    warehouse = _withdrawn_warehouse(tmp_path, notes=notes, notes_present=notes_present)
    recorder = _DbtLackingTables(tmp_path / "run_results.json", warehouse)

    code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), recorder=recorder)

    builds = [argv for argv, _, _ in recorder.calls if argv[:2] == ("dbt", "build")]
    assert not [argv for argv in builds if "source:ourhike.raw_ourhike__notes+" in argv], why
    assert all("source:ourhike.raw_ourhike__disputes+" in argv for argv in builds), "disputes' newest row withdrew it"
    assert code == (build_marts.PARTIAL_EXIT if notes_present else 1), why


def test_the_tables_a_build_may_leave_out_as_withdrawn_are_the_ones_the_extract_may_withdraw():
    """build_marts.py imports only the standard library, so it names the tables itself: the ConditionsQuery tables
    whose database table export_conditions.py's PENDING_READER_SETUP lets go missing."""
    import export_conditions
    from extract._kinds import CONDITIONS_QUERIES

    may_withdraw = {
        f"raw_ourhike__{key}" for key, (table, _) in CONDITIONS_QUERIES.items() if table in export_conditions.PENDING_READER_SETUP
    }
    assert set(build_marts.WITHDRAWABLE) == may_withdraw == {"raw_ourhike__notes", "raw_ourhike__disputes"}
    assert set(build_marts.WITHDRAWABLE.values()) == {"ourhike"}


class _StampedBehind(_DbtRuns):
    """_DbtRuns whose run_results.json is stamped 50 ms before the moment it was written. Linux stamps a file's mtime
    from a coarse clock that can lag time.time() by a few milliseconds, which is how CI's pytest job on 461954c4
    (Pipeline tests, run 37357769435) read a stage A failure's own results as an earlier run's."""

    def __call__(self, argv, *, cwd, env, check):
        completed = super().__call__(argv, cwd=cwd, env=env, check=check)
        if self.results_path.exists():
            behind = time.time() - 0.05
            os.utime(self.results_path, (behind, behind))
        return completed


def test_a_stage_a_failure_is_held_when_the_filesystem_stamps_its_results_behind_the_process_clock(monkeypatch, tmp_path):
    manifest, warehouse = _one_source_setup(tmp_path, monkeypatch)
    failed = [{"unique_id": "model.ourhike.stg_a__club_x", "status": "error", "message": "Conversion Error"}]
    recorder = _StampedBehind(tmp_path / "run_results.json", [(_is_stage_a, 1, failed, {}), (_is_stage_a, 0, [], {})])

    code, _ = _main(monkeypatch, tmp_path, manifest, recorder=recorder)

    assert code == build_marts.PARTIAL_EXIT
    assert _raw_tables(warehouse) == ["raw_a__club_y", "raw_nynjtc__nynjtc_trail_alerts"], "club_x's table is dropped"
    assert len([argv for argv, _, _ in recorder.calls if _is_stage_a(argv)]) == 2


class _StageADiesBeforeWriting(_DbtRuns):
    """_DbtRuns whose stage A exits 1 before writing run_results.json, as dbt does when it dies before running a node."""

    def __call__(self, argv, *, cwd, env, check):
        if _is_stage_a(tuple(argv)):
            self.calls.append((tuple(argv), cwd, env))
            return subprocess.CompletedProcess(argv, 1)
        return super().__call__(argv, cwd=cwd, env=env, check=check)


def test_a_dbt_run_that_writes_no_results_is_never_read_as_the_run_before_it(monkeypatch, tmp_path):
    manifest, warehouse = _one_source_setup(tmp_path, monkeypatch)
    seed_left = [{"unique_id": "model.ourhike.stg_a__club_x", "status": "error"}]
    recorder = _StageADiesBeforeWriting(
        tmp_path / "run_results.json", [(lambda argv: argv[:2] == ("dbt", "seed"), 0, seed_left, {})]
    )

    code, _ = _main(monkeypatch, tmp_path, manifest, recorder=recorder)

    assert code == 1
    assert len(_raw_tables(warehouse)) == 3, "the seed's results name stg_a__club_x, and nothing is dropped for them"


def test_a_failed_test_in_stage_a_is_never_turned_into_a_hold(monkeypatch, tmp_path):
    manifest, warehouse = _one_source_setup(tmp_path, monkeypatch)
    failed = [
        {"unique_id": "model.ourhike.stg_a__club_x", "status": "error"},
        {"unique_id": "test.ourhike.unique_stg_a__club_y_notice_key.1", "status": "fail"},
    ]
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_stage_a, 1, failed, {})])

    code, _ = _main(monkeypatch, tmp_path, manifest, recorder=recorder)

    assert code == 1 and len(_raw_tables(warehouse)) == 3


def test_a_degraded_build_that_was_also_partial_answers_both(monkeypatch, tmp_path):
    processed = tmp_path / "processed"
    results = [
        {"unique_id": "model.ourhike.pub_conditions_closures", "status": "success"},
        {"unique_id": "model.ourhike.pub_conditions_notices", "status": "error"},
    ]
    recorder = _DbtRuns(
        tmp_path / "run_results.json",
        [
            (lambda argv: argv[:3] == (*RESTORE, "restore"), 2, [], {}),
            (_is_writers_run, 1, results, {processed / "conditions_closures.json": "{}"}),
        ],
    )

    code, _ = _main(
        monkeypatch,
        tmp_path,
        _conditions_writers_manifest(tmp_path),
        recorder=recorder,
        extra=("--history-on-failure", "degrade"),
    )

    assert code == build_marts.DEGRADED_PARTIAL_EXIT


@pytest.mark.parametrize("exit_code", [build_marts.PARTIAL_EXIT, build_marts.DEGRADED_PARTIAL_EXIT])
@pytest.mark.parametrize("which", [_is_stage_a, _is_writers_run])
def test_a_dbt_run_that_answers_a_publishable_exit_itself_is_answered_as_a_plain_failure(monkeypatch, tmp_path, exit_code, which):
    """publish-conditions.yml publishes on PARTIAL_EXIT and DEGRADED_PARTIAL_EXIT, so only build_marts.py may give them."""
    recorder = _DbtRuns(tmp_path / "run_results.json", [(which, exit_code, [], {})])

    code, _ = _main(monkeypatch, tmp_path, _conditions_writers_manifest(tmp_path), recorder=recorder)

    assert code == 1


# --- Elementary's checks (build_marts.py's docstring, "ELEMENTARY'S CHECKS RUN AFTER THE WRITERS") -----------------


def _is_checks_run(argv: tuple[str, ...]) -> bool:
    return argv[:2] == ("dbt", "test")


def _checks(runs: list[build_marts.Run]) -> build_marts.Run:
    (checks,) = [run for run in runs if run.stage == build_marts.CHECKS]
    return checks


def test_the_checks_tag_here_is_the_one_both_generators_write():
    import make_dbt_staging

    assert build_marts.ELEMENTARY_CHECK == make_dbt_staging.ELEMENTARY_CHECK
    assert NO_CHECKS == f"tag:{make_dbt_staging.ELEMENTARY_CHECK}"


def test_the_checks_switch_here_is_the_one_every_check_reads():
    import make_dbt_staging

    ((name, value),) = build_marts.CHECKS_SWITCH
    assert make_dbt_staging.ELEMENTARY_ENABLED == f"{{{{ env_var('{name}', 'false') == '{value}' }}}}"


@pytest.mark.parametrize(
    ("lane", "checks"), [(None, None), ("monthly", None), ("hourly", True)], ids=["no lane", "monthly", "hourly asked"]
)
def test_the_checks_switch_is_on_for_elementarys_tables_and_the_checks_pass_alone(lane, checks):
    """Enabled, the checks cost every dbt command its parse, so only the two that need them in the graph carry the
    switch: Elementary's own tables, whose dbt_tests the data-quality file reads each check's lineage from, and the
    pass (make_dbt_staging.ELEMENTARY_ENABLED)."""
    history = History("s3://bucket/history/ci", False, "python")
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=lane is None, lane=lane, checks=checks, history=history)

    assert [(run.label, run.env) for run in runs if run.env] == [
        (build_marts.ELEMENTARY_TABLES, build_marts.CHECKS_SWITCH),
        (build_marts.ELEMENTARY_CHECKS, build_marts.CHECKS_SWITCH),
    ]


@pytest.mark.parametrize(("lane", "checks"), [("hourly", None), (None, False)], ids=["hourly", "no lane, asked for none"])
def test_a_build_that_runs_no_checks_never_turns_their_switch_on(lane, checks):
    """The hourly lane, which runs none yet, would otherwise load all 1,979 into Elementary's dbt_tests every hour."""
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=lane is None, lane=lane, checks=checks)

    assert [run.label for run in runs if run.env] == []


def test_main_gives_the_checks_switch_to_elementarys_tables_and_the_pass_and_to_no_other_command(monkeypatch, tmp_path):
    monkeypatch.setenv("OURHIKE_ELEMENTARY_CHECKS", "true")  # set outside: still no other command's
    _, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES))

    switched = [argv[:2] for argv, _, env in recorder.calls if env.get("OURHIKE_ELEMENTARY_CHECKS") == "true"]
    assert switched == [ELEMENTARY, ("dbt", "test")]
    assert all(env.get("OURHIKE_ELEMENTARY") == "true" for _, _, env in recorder.calls), "never without Elementary's own"


@pytest.mark.parametrize("lane", [None, "monthly", "hourly"])
@pytest.mark.parametrize("manifest", [None, NONE_ALONE, HEAVY], ids=["unplanned", "none alone", "split"])
def test_every_dbt_build_leaves_elementarys_checks_out_split_or_not(lane, manifest):
    """A check built beside its model would run before the writers and at the build's threads, and an anomaly check
    that errors there would fail the build (decision 102's "never blocks a publish"), so no dbt build selects one."""
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, manifest=manifest)

    builds = [run for run in runs if run.argv[:2] == ("dbt", "build")]
    assert builds
    for run in builds:
        assert NO_CHECKS in run.argv[run.argv.index("--exclude") :], run.label
        assert not any(argument.startswith(NO_CHECKS) for argument in run.argv[: run.argv.index("--exclude")]), run.label


def test_the_checks_run_after_the_writers_and_before_the_save_at_one_thread_whatever_the_builds_threads():
    history = History("s3://bucket/history/ci", False, "python")
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=True, threads=4, history=history)

    stages = [run.stage for run in runs]
    at = stages.index(build_marts.CHECKS)
    assert stages.count(build_marts.CHECKS) == 1
    assert runs[at - 1].stage == build_marts.WRITERS and runs[at + 2].label == build_marts.SAVE_LABEL
    assert runs[at + 1].stage == build_marts.DATA_QUALITY, "the data-quality file reads what the checks recorded"
    assert (runs[at].label, runs[at].argv, runs[at].cwd) == (build_marts.ELEMENTARY_CHECKS, *CHECKS_RUN)


def test_the_monthly_lanes_checks_leave_out_what_its_writers_do_and_train_on_its_own_window():
    runs = plan([*PAIR, SQUARES], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly")

    assert _checks(runs).argv == (
        "dbt",
        "test",
        "--profiles-dir",
        ".",
        "--threads",
        "1",
        "-s",
        NO_CHECKS,
        "--exclude",
        *build_marts.LANE_EXCLUDES,
        "source:derived.weather_squares+",
        "--vars",
        '{"days_back": 400}',
    )
    assert build_marts.MONTHLY_TRAINING_DAYS == 400, "pipeline/ELT.md's 'about 400 days' (dbt_project.yml says why --vars)"


@pytest.mark.parametrize("state", [None, Path("/m/target")], ids=["no state", "deferred"])
def test_hourly_lane_checks_run_apart_so_its_build_runs_none_and_writes_no_data_quality_file(state):
    """Decision 110 (build_marts.py's docstring, "THE HOURLY LANE'S CHECKS RUN APART"): every check, every hour, in a
    run of their own after the build has published; the file that counts them is that run's, one writer an hour."""
    assert build_marts.HOURLY_LANE_CHECKS == build_marts.APART
    assert [build_marts.runs_checks(lane) for lane in (None, "monthly", "hourly")] == [True, True, False]
    assert [build_marts.checks_apart(lane) for lane in (None, "monthly", "hourly")] == [False, False, True]
    runs = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", state=state)

    assert not {build_marts.CHECKS, build_marts.DATA_QUALITY} & {run.stage for run in runs}
    assert not [run.label for run in runs if run.env], "nor the checks' switch on Elementary's tables"


#: The record an hourly build writes into its warehouse last (build_marts.write_build_record()), as the UA leg's would
#: read after a green hour: what plan_checks() reads.
HOURLY_STORE = "s3://bucket/history/conditions_ua"
RECORD = {
    "lane": "hourly",
    "started_at": "2026-10-08 21:40:07",
    "built_by": "4ad88f3b72bc run 7.1",
    "without": [],
    "state": None,
    "history_url": HOURLY_STORE,
    "row_history": "on",
    "elementary_saved": True,
    "exit": 0,
}
#: The hourly lane's checks pass over PAIR, whose two steps are the monthly lane's and so are held.
HOURLY_CHECKS_ARGV = (
    "dbt",
    "test",
    "--profiles-dir",
    ".",
    "--threads",
    "1",
    "-s",
    f"{NO_CHECKS},config.meta.cadence:hourly+",
    f"{NO_CHECKS},config.meta.cadence:daily+",
    "--exclude",
    "source:derived.dem_samples+",
    "source:derived.formed_routes+",
    "--indirect-selection",
    "cautious",
)


def _plan_checks(record: dict | None = None, steps: list[Step] | None = None, **options) -> list[build_marts.Run]:
    history = History(HOURLY_STORE, False, "python", on_failure="degrade")
    return build_marts.plan_checks(
        PAIR if steps is None else steps,
        dbt="dbt",
        paths=PATHS,
        lane="hourly",
        record=RECORD if record is None else record,
        **{"history": history, **options},
    )


def test_plan_checks_restores_elementarys_history_alone_then_runs_its_tables_the_checks_and_the_file_then_saves_it():
    runs = _plan_checks()

    assert [run.label for run in runs] == [
        build_marts.ELEMENTARY_RESTORE_LABEL,
        build_marts.ELEMENTARY_TABLES,
        build_marts.ELEMENTARY_CHECKS,
        build_marts.DATA_QUALITY_LABEL,
        build_marts.ELEMENTARY_SAVE_LABEL,
    ]
    store = ("--url", HOURLY_STORE, "--warehouse", "/w/warehouse.duckdb", "--elementary-only")
    policy = ("--elementary-on-failure", "degrade")
    assert runs[0].argv == ("python", "row_history.py", "restore", *store, *policy)
    assert runs[-1].argv == ("python", "row_history.py", "save", *store, "--keep-days", "21", *policy)
    assert (runs[1].argv, runs[1].env) == (ELEMENTARY_RUN[0], build_marts.CHECKS_SWITCH), "dbt_tests describes each check"
    assert (runs[2].argv, runs[2].env, runs[2].stage) == (HOURLY_CHECKS_ARGV, build_marts.CHECKS_SWITCH, build_marts.CHECKS)
    assert runs[3].argv == (
        "dbt",
        "build",
        "--profiles-dir",
        ".",
        "-s",
        "pub_conditions_data_quality",
        "--exclude",
        NO_CHECKS,
        "source:derived.dem_samples+",
        "source:derived.formed_routes+",
        "--indirect-selection",
        "cautious",
    )
    assert runs[3].stage == build_marts.DATA_QUALITY and not runs[3].env


def test_plan_checks_of_a_build_that_saved_no_elementary_history_neither_restores_nor_saves_it():
    """The build's inputs were short (--no-history-save) or its history failed: its warehouse's own Elementary tables, the
    history it restored and its own results, are what the checks read, and nothing joins the training set."""
    runs = _plan_checks({**RECORD, "elementary_saved": False})

    assert [run.label for run in runs] == [
        build_marts.ELEMENTARY_TABLES,
        build_marts.ELEMENTARY_CHECKS,
        build_marts.DATA_QUALITY_LABEL,
    ]


def test_plan_checks_leaves_out_the_steps_the_build_held_and_a_degraded_builds_snapshots_as_the_build_did():
    runs = _plan_checks({**RECORD, "without": ["step_weather_squares"], "row_history": "off"}, steps=[*PAIR, SQUARES])

    checks, quality = _checks(runs).argv, runs[-2].argv
    assert "source:derived.weather_squares+" in checks[checks.index("--exclude") :]
    assert quality[quality.index("--exclude") :] == (
        "--exclude",
        NO_CHECKS,
        "source:derived.dem_samples+",
        "source:derived.formed_routes+",
        "source:derived.weather_squares+",
        build_marts.SNAPSHOTS,
        "--indirect-selection",
        "cautious",
    )


def test_plan_checks_with_no_history_save_restores_elementarys_history_and_saves_none_back():
    runs = _plan_checks(save_history=False)

    assert runs[0].label == build_marts.ELEMENTARY_RESTORE_LABEL and runs[-1].stage == build_marts.DATA_QUALITY


@pytest.mark.parametrize(
    ("lane", "record", "why"),
    [
        ("monthly", RECORD, "runs its own"),
        ("hourly", {**RECORD, "lane": "monthly"}, "the monthly lane's"),
        ("hourly", {**RECORD, "state": "/m/target"}, "a checks run does not have"),
        ("hourly", {**RECORD, "without": ["step_nothing"]}, "name no entry of STEPS"),
    ],
    ids=["a lane that checks in its build", "another lane's record", "a deferred build", "an unknown held step"],
)
def test_plan_checks_refuses_what_a_checks_run_cannot_follow(lane, record, why):
    with pytest.raises(ValueError, match=why):
        build_marts.plan_checks(PAIR, dbt="dbt", paths=PATHS, lane=lane, record=record)


def test_the_build_record_round_trips_through_the_warehouse_and_a_warehouse_without_one_is_refused(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    duckdb.connect(str(warehouse)).close()
    with pytest.raises(ValueError, match="holds no build record"):
        build_marts.read_build_record(warehouse)
    with pytest.raises(ValueError, match="there is none at"):
        build_marts.read_build_record(tmp_path / "elsewhere.duckdb")

    build_marts.write_build_record(warehouse, {**RECORD, "exit": 4})
    build_marts.write_build_record(warehouse, RECORD)

    assert build_marts.read_build_record(warehouse) == RECORD, "one row, the last build's"


def _hourly_main(monkeypatch, tmp_path, codes: dict[int, int] | None = None, extra: tuple[str, ...] = ()):
    """main() as publish-conditions.yml's build step runs it, over a warehouse file that exists, as dbt's would."""
    duckdb.connect(str(tmp_path / "warehouse.duckdb")).close()
    # _manifest() holds no step_<name> exposure for lane_problems() to read.
    monkeypatch.setattr(build_marts, "lane_problems", lambda manifest, steps, lane: [])
    return _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes=codes, extra=("--lane", "hourly", *extra))


def test_an_hourly_build_writes_its_record_last_saying_when_it_started_and_that_it_saved_elementarys_history(
    monkeypatch, tmp_path, capsys
):
    code, recorder = _hourly_main(monkeypatch, tmp_path, extra=("--without-step", "step_weather_squares"))

    record = build_marts.read_build_record(tmp_path / "warehouse.duckdb")
    (started,) = {env["OURHIKE_BUILD_STARTED_AT"] for _, _, env in recorder.calls}
    assert code == 0 and recorder.calls[-1][0][:3] == (*RESTORE, "save")
    assert record == {
        "lane": "hourly",
        "started_at": started,
        "built_by": "abc123 run 7.1",
        "without": ["step_weather_squares"],
        "state": None,
        "history_url": str(tmp_path / "history"),
        "row_history": "on",
        "elementary_saved": True,
        "exit": 0,
    }
    assert f"{build_marts.BUILD_RECORD} written for the checks after this build" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("codes", "extra", "row_history", "exit_code"),
    [
        ({}, ("--no-history-save",), "on", 0),
        ({1: build_marts.ELEMENTARY_DEGRADED_EXIT}, ("--history-on-failure", "degrade"), "on", build_marts.PARTIAL_EXIT),
        ({1: 1}, ("--history-on-failure", "degrade"), "off", build_marts.DEGRADED_EXIT),
    ],
    ids=["no history save", "elementary's restore degraded", "row history not restored"],
)
def test_an_hourly_build_that_saved_no_elementary_history_says_so_in_its_record(
    monkeypatch, tmp_path, codes, extra, row_history, exit_code
):
    """So its checks restore nothing and save nothing (plan_checks()): the history they would build on is not this
    build's, or this build's inputs were short."""
    code, _ = _hourly_main(monkeypatch, tmp_path, codes=codes, extra=extra)

    record = build_marts.read_build_record(tmp_path / "warehouse.duckdb")
    assert code == exit_code
    assert (record["elementary_saved"], record["row_history"], record["exit"]) == (False, row_history, exit_code)


@pytest.mark.parametrize("lane", [(), ("--lane", "monthly")], ids=["no lane", "monthly"])
def test_a_build_whose_checks_run_in_it_writes_no_record(monkeypatch, tmp_path, lane):
    duckdb.connect(str(tmp_path / "warehouse.duckdb")).close()
    monkeypatch.setattr(build_marts, "lane_problems", lambda manifest, steps, lane: [])
    _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), extra=lane)

    with pytest.raises(ValueError, match="holds no build record"):
        build_marts.read_build_record(tmp_path / "warehouse.duckdb")


def test_a_record_that_cannot_be_written_is_a_warning_and_the_build_and_its_exit_stand(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(build_marts, "lane_problems", lambda manifest, steps, lane: [])
    code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), extra=("--lane", "hourly"))

    assert code == 0
    assert "::warning title=No build record::" in capsys.readouterr().out


def _checks_main(
    monkeypatch,
    tmp_path,
    record: dict | None = None,
    codes: dict[int, int] | None = None,
    extra: tuple[str, ...] = (),
    recorder: _Recorder | None = None,
) -> tuple[int, _Recorder]:
    """main() as check-conditions.yml runs it: over the warehouse an hourly build left, whose record names _main()'s
    history store."""
    warehouse = tmp_path / "warehouse.duckdb"
    build_marts.write_build_record(warehouse, {**RECORD, "history_url": str(tmp_path / "history"), **(record or {})})
    return _main(
        monkeypatch,
        tmp_path,
        _manifest(*STEP_TABLES),
        codes=codes,
        extra=("--lane", "hourly", "--checks-only", *extra),
        recorder=recorder,
    )


def test_the_checks_run_runs_plan_checks_with_the_builds_start_and_switches_the_checks_on_where_they_run(monkeypatch, tmp_path):
    code, recorder = _checks_main(monkeypatch, tmp_path)

    store = str(tmp_path / "history")  # as _main() names it, before any resolving
    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    expected = build_marts.plan_checks(
        STEPS,
        dbt="dbt",
        paths=paths,
        lane="hourly",
        record={**RECORD, "history_url": store},
        history=History(store, True, "python"),
    )
    assert code == 0
    assert [(argv, cwd) for argv, cwd, _ in recorder.calls] == argvs(expected)
    assert {env["OURHIKE_BUILD_STARTED_AT"] for _, _, env in recorder.calls} == {RECORD["started_at"]}, "the build's"
    switched = [argv[:2] for argv, _, env in recorder.calls if env.get("OURHIKE_ELEMENTARY_CHECKS") == "true"]
    assert switched == [ELEMENTARY, ("dbt", "test")]


def test_the_checks_run_of_a_degraded_build_renders_the_project_with_the_row_history_off_as_it_did(monkeypatch, tmp_path):
    _, recorder = _checks_main(monkeypatch, tmp_path, record={"row_history": "off"})

    assert {env.get("OURHIKE_ROW_HISTORY") for _, _, env in recorder.calls} == {"off"}


def test_a_checks_run_whose_data_quality_file_failed_saves_elementarys_history_and_exits_1(monkeypatch, tmp_path, capsys):
    """The file is that run's one product, so a pass that fails after its retries ends it red, with nothing to publish;
    the checks it ran still join the history."""
    recorder = _DbtRuns(
        tmp_path / "run_results.json",
        [(_is_quality_run, 1, [{"unique_id": "model.ourhike.pub_conditions_data_quality", "status": "error"}], {})],
    )
    code, recorder = _checks_main(monkeypatch, tmp_path, recorder=recorder)

    out = capsys.readouterr().out
    assert code == 1
    assert len(recorder.retries) == build_marts.DBT_RETRIES
    assert recorder.calls[-1][0][:3] == (*RESTORE, "save") and "--elementary-only" in recorder.calls[-1][0]
    assert "::error title=Data-quality file not written::" in out and "goes red once Elementary's history is saved" in out
    assert not (tmp_path / "run_results.json").exists(), "nothing for publish.py --sidecar to read as written"


@pytest.mark.parametrize("which", [1, -1], ids=["restore", "save"])
def test_a_checks_run_whose_elementary_history_degraded_still_writes_the_file_and_exits_partial(monkeypatch, tmp_path, which):
    calls = len(_checks_main(monkeypatch, tmp_path)[1].calls)
    position = 1 if which == 1 else calls

    code, recorder = _checks_main(
        monkeypatch,
        tmp_path,
        codes={position: build_marts.ELEMENTARY_DEGRADED_EXIT},
        extra=("--history-on-failure", "degrade"),
    )

    assert code == build_marts.PARTIAL_EXIT
    assert len(recorder.calls) == calls, "the checks, the file and the save all still run"


def test_a_checks_run_whose_restore_fails_without_degrade_stops_before_its_checks(monkeypatch, tmp_path):
    code, recorder = _checks_main(monkeypatch, tmp_path, codes={1: 1})

    assert code == 1 and len(recorder.calls) == 1


def test_a_checks_run_does_not_go_red_for_the_tables_its_build_found_withdrawn(monkeypatch, tmp_path, capsys):
    """The build's own run already went red for them; its checks leave them out as its builds did, quietly."""
    monkeypatch.setattr(build_marts, "withdrawn_tables", lambda warehouse: ("raw_ourhike__notes",))
    code, recorder = _checks_main(monkeypatch, tmp_path)

    (checks,) = [argv for argv, _, _ in recorder.calls if _is_checks_run(argv)]
    assert code == 0 and "source:ourhike.raw_ourhike__notes+" in checks
    assert "withdrawn::" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("record", "extra", "why"),
    [
        ({"history_url": "s3://bucket/history/conditions_production"}, (), "pass that store as --history-url"),
        ({}, ("--without-step", "step_weather_squares"), "takes the build's held steps from its record"),
    ],
    ids=["another leg's store", "held steps given twice"],
)
def test_a_checks_run_refuses_what_would_not_follow_its_build(monkeypatch, tmp_path, capsys, record, extra, why):
    with pytest.raises(SystemExit) as stopped:
        _checks_main(monkeypatch, tmp_path, record=record, extra=extra)

    assert stopped.value.code == 2 and why in capsys.readouterr().err


def test_a_checks_run_over_a_warehouse_no_hourly_build_recorded_is_refused(monkeypatch, tmp_path, capsys):
    duckdb.connect(str(tmp_path / "warehouse.duckdb")).close()
    with pytest.raises(SystemExit):
        _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), extra=("--lane", "hourly", "--checks-only"))

    assert "holds no build record" in capsys.readouterr().err


def test_the_checks_leave_out_each_raw_table_the_warehouse_does_not_hold():
    absent = ("source:bmta.raw_bmta__bmta_alerts_pdf", "source:tatc.raw_tatc__tatc_ridgerunner_reports")
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=True, absent=absent)

    checks = _checks(runs).argv
    assert checks[checks.index("--exclude") :] == ("--exclude", *absent)
    assert all(not set(absent) & set(run.argv) for run in runs if run.stage != build_marts.CHECKS), "the builds read them"


def _source(name: str, table: str, cadence: str, schema: str = "raw") -> tuple[str, dict]:
    return f"source.ourhike.{name}.{table}", {
        "source_name": name,
        "name": table,
        "schema": schema,
        "config": {"meta": {"cadence": cadence}},
    }


def test_absent_sources_names_each_raw_table_of_the_lane_that_the_warehouse_does_not_hold(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema raw")
        con.execute("create table raw.raw_atc__shelters (x integer)")
        con.execute("create view raw.raw_nws__alerts as select 1 as x")
    manifest = {
        "sources": dict(
            [
                _source("atc", "raw_atc__shelters", "monthly"),
                _source("atc", "raw_atc__never_landed", "monthly"),
                _source("nws", "raw_nws__alerts", "hourly"),
                _source("bmta", "raw_bmta__bmta_alerts_pdf", "daily"),
                _source("derived", "dem_samples", "monthly", schema="derived"),
            ]
        ),
        "child_map": {},
    }

    assert build_marts.absent_sources(manifest, warehouse, None) == (
        "source:atc.raw_atc__never_landed",
        "source:bmta.raw_bmta__bmta_alerts_pdf",
    )
    assert build_marts.absent_sources(manifest, warehouse, "monthly") == ("source:atc.raw_atc__never_landed",)
    assert build_marts.absent_sources(manifest, warehouse, "hourly") == ("source:bmta.raw_bmta__bmta_alerts_pdf",)
    assert build_marts.absent_sources(manifest, tmp_path / "no_warehouse.duckdb", None) == ()


def test_main_leaves_out_the_checks_on_the_raw_tables_the_warehouse_lacks_when_the_pass_starts(monkeypatch, tmp_path, capsys):
    """Read when the pass starts, not after the seeds: a source whose own model failed in stage A has its raw tables
    dropped then (one_sources_failures()), and its checks would error on them."""
    warehouse = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("create schema raw")
        con.execute("create table raw.raw_atc__shelters (x integer)")
        con.execute("create table raw.raw_amc__alerts (x integer)")
    manifest = _manifest(*STEP_TABLES)
    manifest["sources"] |= dict([_source("atc", "raw_atc__shelters", "monthly"), _source("amc", "raw_amc__alerts", "hourly")])

    class Dropping(_Recorder):
        def __call__(self, argv, *, cwd, env, check):
            if _is_writers_run(tuple(argv)):  # as if stage A had held amc and dropped its table
                build_marts.drop_raw_tables(warehouse, ["raw_amc__alerts"])
            return super().__call__(argv, cwd=cwd, env=env, check=check)

    code, recorder = _main(monkeypatch, tmp_path, manifest, recorder=Dropping())

    (checks,) = [argv for argv, _, _ in recorder.calls if _is_checks_run(argv)]
    assert code == 0
    assert checks[checks.index("--exclude") :] == ("--exclude", "source:amc.raw_amc__alerts")
    assert "-- build_marts: Elementary's checks leave out 1 raw table(s) this warehouse does not hold: amc.raw_amc__alerts" in (
        capsys.readouterr().out
    )


def test_a_warehouse_the_checks_pass_cannot_read_leaves_nothing_out_and_stops_nothing(monkeypatch, tmp_path, capsys):
    """The pass never stops a build, so neither may the read before it: a DuckDB error there runs every check."""

    def unreadable(*_args, **_kwargs):
        raise OSError("IO Error: Could not set lock on file")

    monkeypatch.setattr(build_marts, "absent_sources", unreadable)

    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES))

    (checks,) = [argv for argv, _, _ in recorder.calls if _is_checks_run(argv)]
    assert code == 0 and recorder.calls[-1][0][:3] == (*RESTORE, "save")
    assert "--exclude" not in checks
    assert (
        "-- build_marts: Elementary's checks: the warehouse's raw tables were not read (IO Error: Could not set lock on file)"
        in capsys.readouterr().out
    )


CHECK_RESULTS = [
    {
        "unique_id": "test.ourhike.elementary_source_volume_anomalies_bmta_raw_bmta__alerts_.1",
        "status": "error",
        "message": "Catalog Error: Table with name raw_bmta__alerts does not exist!\nLINE 14: from raw_bmta__alerts",
    },
    {"unique_id": "test.ourhike.elementary_volume_anomalies_closures_v1_.2", "status": "warn", "message": "Got 1 result"},
    {"unique_id": "test.ourhike.elementary_source_schema_changes_atc_raw_atc__shelters_.3", "status": "pass"},
]


def test_a_check_that_errors_is_annotated_and_changes_neither_the_builds_exit_nor_its_save(monkeypatch, tmp_path, capsys):
    """Decision 102: the checks never block a publish. A check that errors is said in the log and as an annotation,
    never retried, and the build goes on to save its history and answers as it would have without the pass."""
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_checks_run, 1, CHECK_RESULTS, {})])

    code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), recorder=recorder)

    out = capsys.readouterr().out
    assert code == 0
    commands = [argv for argv, _, _ in recorder.calls]
    assert commands[-3][:2] == ("dbt", "test") and commands[-1][:3] == (*RESTORE, "save")
    assert _is_quality_run(commands[-2]), "and the data-quality file is written from what they recorded"
    assert recorder.retries == [], "a `dbt test` is never retried"
    assert "-- build_marts: Elementary's checks: 3 check(s), 1 error, 1 pass, 1 warn; exit 1" in out
    assert (
        "-- build_marts: Elementary's checks: error: ourhike.elementary_source_volume_anomalies_bmta_raw_bmta__alerts_.1: "
        "Catalog Error: Table with name raw_bmta__alerts does not exist!\n" in out
    ), "the message's first line alone"
    assert "-- build_marts: Elementary's checks: warn: ourhike.elementary_volume_anomalies_closures_v1_.2\n" in out
    assert (
        "::warning title=Elementary's checks errored::1 check(s) errored (exit 1): "
        "ourhike.elementary_source_volume_anomalies_bmta_raw_bmta__alerts_.1." in out
    )
    assert "::error" not in out


def test_a_partial_build_answers_partial_whatever_its_checks_say(monkeypatch, tmp_path):
    processed = tmp_path / "processed"
    writers = [
        {"unique_id": "model.ourhike.pub_conditions_closures", "status": "success"},
        {"unique_id": "model.ourhike.pub_conditions_notices", "status": "error", "message": "TopologyException"},
    ]
    recorder = _DbtRuns(
        tmp_path / "run_results.json",
        [
            (_is_writers_run, 1, writers, {processed / "conditions_closures.json": "{}"}),
            (_is_checks_run, 1, CHECK_RESULTS, {}),
        ],
    )

    code, _ = _main(monkeypatch, tmp_path, _conditions_writers_manifest(tmp_path), recorder=recorder)

    assert code == build_marts.PARTIAL_EXIT


def test_checks_that_only_warn_are_counted_and_named_with_no_annotation(monkeypatch, tmp_path, capsys):
    """Warnings are the design (CONTRACT.md's run order, step 4): the data-quality page reads them, not the log."""
    recorder = _DbtRuns(tmp_path / "run_results.json", [(_is_checks_run, 0, CHECK_RESULTS[1:], {})])

    code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), recorder=recorder)

    out = capsys.readouterr().out
    assert code == 0
    assert "-- build_marts: Elementary's checks: 2 check(s), 1 pass, 1 warn; exit 0" in out
    assert "::warning title=Elementary" not in out


class _ChecksCrash(_Recorder):
    """_Recorder whose checks pass exits 2 and leaves no run_results.json, as a dbt that crashed would."""

    def __call__(self, argv, *, cwd, env, check):
        completed = super().__call__(argv, cwd=cwd, env=env, check=check)
        return subprocess.CompletedProcess(argv, 2) if _is_checks_run(tuple(argv)) else completed


def test_a_checks_pass_that_leaves_no_results_says_so_and_stops_nothing(monkeypatch, tmp_path, capsys):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), recorder=_ChecksCrash())

    out = capsys.readouterr().out
    assert code == 0 and recorder.calls[-1][0][:3] == (*RESTORE, "save")
    assert "::warning title=Elementary's checks recorded nothing::the checks pass ended with exit 2" in out


def test_a_checks_pass_that_selects_nothing_is_annotated_because_every_lane_has_checks():
    lines = build_marts.checks_report([], 0)

    assert lines[0] == "-- build_marts: Elementary's checks: 0 check(s), none selected; exit 0"
    assert lines[1].startswith("::warning title=Elementary's checks ran none::the checks pass selected no check (exit 0)")
    assert len(lines) == 2


@pytest.mark.parametrize("results", [[], None], ids=["none selected", "no results left"])
def test_a_pass_of_what_a_change_reaches_that_reaches_no_check_is_an_answer_with_no_annotation(results):
    """Decision 111: a pull request that changes only a pub_ writer, which carries no check, selects none."""
    lines = build_marts.checks_report(results, 0, none_is_an_answer=True)

    assert lines == [
        "-- build_marts: Elementary's checks: 0 check(s), none selected; exit 0",
        "-- build_marts: Elementary's checks: nothing this change reaches carries a check",
    ]


def test_a_pass_of_what_a_change_reaches_that_failed_without_results_is_still_annotated():
    assert build_marts.checks_report(None, 2, none_is_an_answer=True)[0].startswith("::warning title=Elementary's checks")


# --- decision 111: a pull request runs the checks its change reaches ------------------------------------------------


def test_given_a_base_the_checks_pass_selects_what_state_modified_reaches_from_its_target():
    """build_marts.py's docstring, "A PULL REQUEST RUNS THE CHECKS ITS CHANGE REACHES": dbt's own state:modified+,
    against the base project's target/, as the maintainer asked ("Run all of them that have been modified, and
    downstream models")."""
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=True, checks_base=Path("/b/pipeline/dbt"))

    assert _checks(runs).argv == (
        "dbt",
        "test",
        "--profiles-dir",
        ".",
        "--threads",
        "1",
        "-s",
        f"{NO_CHECKS},state:modified+",
        "--state",
        "/b/pipeline/dbt/target",
    )
    assert [run.argv for run in runs if run.stage != build_marts.CHECKS] == [
        run.argv for run in plan([], dbt="dbt", python="python", paths=PATHS, fixtures=True) if run.stage != build_marts.CHECKS
    ], "a base changes the checks pass and nothing else"


@pytest.mark.parametrize("lane", ["monthly", "hourly"])
def test_a_lane_is_refused_a_checks_base_because_each_lane_runs_every_check_it_has(lane):
    with pytest.raises(ValueError, match="runs every check it has"):
        plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, checks_base=Path("/b"))


#: A head manifest with macros, as every real one has, for checks_base_problems() to compare.
MACROS = {
    "macro.ourhike.row_hash": {"macro_sql": "{% macro row_hash() %}md5(x){% endmacro %}"},
    "macro.elementary.test_volume_anomalies": {"macro_sql": "{% test volume_anomalies() %}...{% endtest %}"},
}


def _base(tmp_path: Path, macros: dict | None = None, project: bytes | None = None) -> Path:
    """A base project directory as CI's dbt job leaves it: this project's three files, and a manifest in target/."""
    base = tmp_path / "base" / "pipeline" / "dbt"
    (base / "target").mkdir(parents=True)
    for name in build_marts.CHECKS_BASE_FILES:
        (base / name).write_bytes((DBT_DIR / name).read_bytes())
    if project is not None:
        (base / "dbt_project.yml").write_bytes(project)
    (base / "target" / "manifest.json").write_text(json.dumps({"macros": MACROS if macros is None else macros}))
    return base


def test_checks_base_problems_finds_none_when_the_base_differs_only_in_what_dbt_compares(tmp_path):
    assert build_marts.checks_base_problems(_base(tmp_path), {"macros": MACROS}) == []


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ("project", "dbt_project.yml differs from the base's, and dbt's state comparison reads no var"),
        ("macro", "1 macro(s) differ from the base's (macro.elementary.test_volume_anomalies)"),
        ("added macro", "1 macro(s) differ from the base's (macro.ourhike.new_one)"),
        ("no manifest", "the base's manifest"),
    ],
)
def test_checks_base_problems_names_each_change_dbts_state_comparison_cannot_see(tmp_path, change, why):
    """Measured 2026-10-08 with `dbt ls` on dbt 2.0.6: a var moved in dbt_project.yml, a comment in
    elementary_overrides.sql and one in Elementary's own test_volume_anomalies.sql each selected 0 of the 1,979 checks."""
    head = {"macros": MACROS}
    if change == "project":
        base = _base(tmp_path, project=(DBT_DIR / "dbt_project.yml").read_bytes() + b"\n# anomaly_sensitivity moved\n")
    elif change == "macro":
        base = _base(tmp_path, macros={**MACROS, "macro.elementary.test_volume_anomalies": {"macro_sql": "old"}})
    elif change == "added macro":
        base = _base(tmp_path)
        head = {"macros": {**MACROS, "macro.ourhike.new_one": {"macro_sql": "{% macro new_one() %}{% endmacro %}"}}}
    else:
        base = _base(tmp_path)
        (base / "target" / "manifest.json").unlink()

    (problem,) = build_marts.checks_base_problems(base, head)
    assert why in problem


def _base_main(monkeypatch, tmp_path, base: Path | None) -> tuple[int, _Recorder]:
    manifest = {**_manifest(*STEP_TABLES), "macros": MACROS}
    return _main(monkeypatch, tmp_path, manifest, extra=("--checks-base", str(base)) if base else ())


def test_main_with_a_base_that_answers_runs_only_what_the_change_reaches_and_says_so(monkeypatch, tmp_path, capsys):
    base = _base(tmp_path)
    code, recorder = _base_main(monkeypatch, tmp_path, base)

    (checks,) = [argv for argv, _, _ in recorder.calls if _is_checks_run(argv)]
    assert code == 0
    assert checks[checks.index("-s") + 1] == f"{NO_CHECKS},state:modified+"
    assert checks[checks.index("--state") + 1] == str(base.resolve() / "target")
    assert f"only the checks on what changed since the base, {base.resolve()}, and below it" in capsys.readouterr().out


def test_main_with_a_base_whose_macros_differ_runs_every_check_and_says_why(monkeypatch, tmp_path, capsys):
    base = _base(tmp_path, macros={"macro.ourhike.row_hash": {"macro_sql": "older"}})
    code, recorder = _base_main(monkeypatch, tmp_path, base)

    (checks,) = [argv for argv, _, _ in recorder.calls if _is_checks_run(argv)]
    out = capsys.readouterr().out
    assert code == 0 and checks == CHECKS_RUN[0]
    assert "every check, not only those this change reaches: 2 macro(s) differ from the base's" in out


def test_main_with_no_base_runs_every_check_and_says_so(monkeypatch, tmp_path, capsys):
    code, recorder = _base_main(monkeypatch, tmp_path, None)

    (checks,) = [argv for argv, _, _ in recorder.calls if _is_checks_run(argv)]
    assert code == 0 and checks == CHECKS_RUN[0]
    assert "every check, since no --checks-base names a base to compare with" in capsys.readouterr().out


def test_main_refuses_a_checks_base_in_a_lane(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit):
        _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), extra=("--lane", "monthly", "--checks-base", str(tmp_path)))

    assert "runs every check it has" in capsys.readouterr().err


def test_the_checks_report_names_ten_errors_and_counts_the_rest():
    results = [{"unique_id": f"test.ourhike.check_{number:02d}", "status": "error", "message": "x" * 300} for number in range(12)]

    lines = build_marts.checks_report(results, 1)

    assert lines[0] == "-- build_marts: Elementary's checks: 12 check(s), 12 error; exit 1"
    assert all(len(line.rsplit(": ", 1)[-1]) == build_marts.FAILED_VALUE_WIDTH for line in lines[1:13])
    assert lines[-1].startswith("::warning title=Elementary's checks errored::12 check(s) errored (exit 1): ourhike.check_00")
    assert "ourhike.check_09 and 2 more." in lines[-1] and "check_10" not in lines[-1]


# --- The data-quality file (build_marts.py's docstring, "THE DATA-QUALITY FILE IS WRITTEN LAST") ---


def _is_quality_run(argv: tuple[str, ...]) -> bool:
    return "-s" in argv and argv[argv.index("-s") + 1] in QUALITY_WRITERS


@pytest.mark.parametrize("lane, writers", [(None, QUALITY_WRITERS), ("monthly", ("pub_data_quality",))])
def test_the_lanes_data_quality_writer_builds_after_the_writers_and_before_the_save_and_the_writers_leave_it(lane, writers):
    """Decision 102's run order: the writers, Elementary's checks, then the file that reads what the checks recorded,
    then the save. The writers' `-s path:models/publish` would take both data-quality writers, so it leaves them out.
    The hourly lane's file is its checks run's (test_plan_checks_restores_elementarys_history_alone_...)."""
    history = History("s3://bucket/history/x", False, "python")
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, history=history)

    quality = runs[-2]
    assert (quality.stage, quality.label, quality.cwd) == (build_marts.DATA_QUALITY, build_marts.DATA_QUALITY_LABEL, DBT_DIR)
    assert quality.argv[: quality.argv.index("-s")] == ("dbt", "build", "--profiles-dir", ".")
    assert quality.argv[quality.argv.index("-s") + 1 :][: len(writers)] == writers
    assert [run.stage for run in runs[-4:-2]] == [build_marts.WRITERS, build_marts.CHECKS]
    assert runs[-1].label == build_marts.SAVE_LABEL
    writers_run = _writers(runs).argv
    assert set(QUALITY_WRITERS) <= set(writers_run[writers_run.index("--exclude") + 1 :])


def test_every_command_gets_one_build_start_in_utc_to_the_second(monkeypatch, tmp_path):
    """macros/data_quality.sql tells this build's results from the lane's history by it."""
    _, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES))

    (start,) = {env.get("OURHIKE_BUILD_STARTED_AT") for _, _, env in recorder.calls}
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", start)
    moment = datetime(2026, 10, 8, 7, 5, 0, 700000, tzinfo=timezone.utc)
    assert build_marts.build_started_at(moment) == "2026-10-08 07:05:00"


def _quality_manifest(tmp_path: Path) -> dict:
    """The conditions writers' manifest, with the two data-quality writers and where each writes."""
    manifest = _conditions_writers_manifest(tmp_path)
    manifest["nodes"]["model.ourhike.pub_data_quality"] = {"config": {"location": "data_quality.json"}}
    manifest["nodes"]["model.ourhike.pub_conditions_data_quality"] = {"config": {"location": "conditions_data_quality.json"}}
    return manifest


WRITERS_RESULTS = [{"unique_id": "model.ourhike.pub_conditions_closures", "status": "success"}]
QUALITY_RESULTS = [
    {"unique_id": "model.ourhike.pub_data_quality", "status": "success"},
    {"unique_id": "model.ourhike.pub_conditions_data_quality", "status": "success"},
]


def test_after_the_data_quality_pass_run_results_hold_the_writers_results_and_its_own(monkeypatch, tmp_path):
    """publish.py proves each phone file written by the run results it reads, and the data-quality pass writes its own
    over the writers': read alone, they would leave every phone file but this one kept, and nothing else published."""
    processed = tmp_path / "processed"
    recorder = _DbtRuns(
        tmp_path / "run_results.json",
        [
            (_is_writers_run, 0, WRITERS_RESULTS, {processed / "conditions_closures.json": "{}"}),
            (_is_quality_run, 0, QUALITY_RESULTS, {processed / "data_quality.json": "{}"}),
        ],
    )

    code, _ = _main(monkeypatch, tmp_path, _quality_manifest(tmp_path), recorder=recorder)

    assert code == 0
    results = json.loads((tmp_path / "run_results.json").read_text())["results"]
    assert [result["unique_id"] for result in results] == [
        "model.ourhike.pub_conditions_closures",
        "model.ourhike.pub_data_quality",
        "model.ourhike.pub_conditions_data_quality",
    ]
    assert (tmp_path / build_marts.WRITERS_RESULTS_NAME).exists(), "kept beside run_results.json, in target/"


def test_a_failed_data_quality_pass_removes_its_file_and_leaves_the_writers_results_and_the_exit_alone(
    monkeypatch, tmp_path, capsys
):
    """Decision 102's checks never block a publish, and nor does the file that reports them: a pass that fails after
    its retries leaves no file to publish, run results that name no data-quality writer (so publish.py keeps the
    bucket's last copy), and the build's exit as the rest of the build made it, with the row history still saved."""
    processed = tmp_path / "processed"
    failed = [{"unique_id": "model.ourhike.pub_data_quality", "status": "error"}]
    recorder = _DbtRuns(
        tmp_path / "run_results.json",
        [
            (_is_writers_run, 0, WRITERS_RESULTS, {processed / "conditions_closures.json": "{}"}),
            (_is_quality_run, 1, failed, {processed / "data_quality.json": '{"format": "ourhike-data-q'}),
        ],
    )

    code, _ = _main(monkeypatch, tmp_path, _quality_manifest(tmp_path), recorder=recorder)

    out = capsys.readouterr().out
    assert code == 0
    assert len(recorder.retries) == build_marts.DBT_RETRIES, "a failed build is retried, this one too"
    assert sorted(path.name for path in processed.iterdir()) == ["conditions_closures.json"]
    assert json.loads((tmp_path / "run_results.json").read_text())["results"] == WRITERS_RESULTS
    assert "::error title=Data-quality file not written::" in out and "data_quality.json is not published" in out
    assert recorder.calls[-1][0][:3] == (*RESTORE, "save")


def test_with_no_writers_results_kept_the_data_quality_pass_leaves_no_run_results_to_misread(tmp_path):
    """Read alone, the pass's own results would say every phone file's writer did not run; with none, publish.py
    refuses for want of run results instead, which is the loud direction."""
    results = _results(tmp_path / "run_results.json", *QUALITY_RESULTS)

    build_marts.data_quality_written(subprocess.CompletedProcess([], 0), {}, tmp_path, results_path=results)

    assert not results.exists()
