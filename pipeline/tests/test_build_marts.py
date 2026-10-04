"""build_marts.py, the one home of the build order: the command lists it plans for zero, one and two Python steps.

Nothing here runs dbt. The plans are compared argument by argument, and
main() runs against a stand-in for subprocess.run, so what is held is the
order, the selectors and the stop on the first failure, not dbt's answers.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
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


def argvs(runs):
    return [(run.argv, run.cwd) for run in runs]


def test_with_no_steps_the_build_is_the_seeds_then_one_build_then_the_writers():
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=True)

    assert argvs(runs) == [
        (("dbt", "seed", "--profiles-dir", "."), DBT_DIR),
        (("dbt", "build", "--profiles-dir", ".", "--exclude", "package:dbt_project_evaluator", "path:models/publish"), DBT_DIR),
        (("dbt", "build", "--profiles-dir", ".", "-s", "path:models/publish"), DBT_DIR),
    ]


def test_one_step_runs_between_stage_a_and_the_build_of_what_its_table_unblocks():
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True)

    assert argvs(runs) == [
        (("dbt", "seed", "--profiles-dir", "."), DBT_DIR),
        (
            (
                "dbt",
                "build",
                "--profiles-dir",
                ".",
                "--exclude",
                "package:dbt_project_evaluator",
                "path:models/publish",
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
            ("dbt", "build", "--profiles-dir", ".", "-s", "source:derived.dem_samples+", "--exclude", "path:models/publish"),
            DBT_DIR,
        ),
        (("dbt", "build", "--profiles-dir", ".", "-s", "path:models/publish"), DBT_DIR),
    ]


def test_with_two_steps_the_first_steps_build_leaves_the_second_tables_descendants_for_later():
    runs = plan([DEM_SAMPLING, SECOND], dbt="dbt", python="python", paths=PATHS, fixtures=True)

    assert [run.argv[:2] for run in runs] == [
        ("dbt", "seed"),
        ("dbt", "build"),
        ("python", "step_dem_sampling.py"),
        ("dbt", "build"),
        ("python", "step_second.py"),
        ("dbt", "build"),
        ("dbt", "build"),
    ]
    after_first, after_second = runs[3].argv, runs[5].argv
    assert after_first[after_first.index("-s") :] == (
        "-s",
        "source:derived.dem_samples+",
        "--exclude",
        "path:models/publish",
        "source:derived.graph_pieces+",
    )
    assert after_second[after_second.index("-s") :] == (
        "-s",
        "source:derived.graph_pieces+",
        "--exclude",
        "path:models/publish",
    )
    assert runs[4].argv == ("python", "step_second.py", "--warehouse", "/w/warehouse.duckdb")
    assert runs[-1].argv == ("dbt", "build", "--profiles-dir", ".", "-s", "path:models/publish")


def test_without_fixtures_a_step_gets_no_fixture_arguments_and_reads_its_own_defaults():
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=False)

    assert runs[2].argv == ("python", "step_dem_sampling.py", "--warehouse", "/w/warehouse.duckdb")


def test_threads_reach_every_dbt_seed_and_build_and_no_step():
    runs = plan([DEM_SAMPLING, SECOND], dbt="dbt", python="python", paths=PATHS, fixtures=True, threads=2)

    for run in runs:
        assert ("--threads" in run.argv) == (run.argv[0] == "dbt"), run.argv
        if run.argv[0] == "dbt":
            assert run.argv[run.argv.index("--threads") + 1] == "2"


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


def _main(
    monkeypatch, tmp_path, manifest: dict, codes: dict[int, int] | None = None, extra: tuple[str, ...] = ()
) -> tuple[int, _Recorder]:
    recorder = _Recorder(codes)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(build_marts, "MANIFEST_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(build_marts.subprocess, "run", recorder)
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
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES))

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    assert code == 0
    assert [(argv, cwd) for argv, cwd, _ in recorder.calls] == argvs(
        plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True, history=_history(tmp_path))
    )
    assert recorder.calls[0][0][:3] == (*RESTORE, "restore") and recorder.calls[-1][0][:3] == (*RESTORE, "save")
    for _, _, env in recorder.calls:
        assert env["OURHIKE_WAREHOUSE"] == str(tmp_path / "warehouse.duckdb")
        assert env["OURHIKE_PROCESSED_DIR"] == str(tmp_path / "processed")
        assert env["TZ"] == "UTC", "macros/row_hash.sql: a TIMESTAMPTZ hashes in the session's zone"
    assert (tmp_path / "processed").is_dir(), "COPY creates no directory, so the writers' folder must exist first"


def test_main_stops_at_the_first_command_that_fails_and_answers_with_its_exit_code(monkeypatch, tmp_path):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={3: 2})

    assert code == 2
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ("dbt", "seed"), ("dbt", "build")]
    assert not [argv for argv, _, _ in recorder.calls if argv[2:3] == ("save",)], "a failed build never saves"


def test_main_refuses_after_the_seeds_when_a_derived_source_has_no_step(monkeypatch, tmp_path, capsys):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES, "unwritten"))

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ("dbt", "seed")]
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
    runs = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly")
    everything = plan(PAIR, dbt="dbt", python="python", paths=PATHS, fixtures=False)

    assert [run.label for run in runs] == [run.label for run in everything]
    for lane_run, full_run in zip(runs, everything, strict=True):
        if full_run.argv[:2] != ("dbt", "build"):
            assert lane_run.argv == full_run.argv, "the seeds and the Python steps are the same in every lane"
        elif "--exclude" in full_run.argv:
            assert lane_run.argv == full_run.argv + build_marts.LANE_EXCLUDES
        else:
            assert lane_run.argv == full_run.argv + ("--exclude", *build_marts.LANE_EXCLUDES)


def test_the_monthly_lanes_writers_leave_the_hourly_writers_unrun():
    writers = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly")[-1]

    assert writers.argv == (
        "dbt",
        "build",
        "--profiles-dir",
        ".",
        "-s",
        "path:models/publish",
        "--exclude",
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
                "path:models/publish",
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
                "source:derived.dem_samples+",
                "source:derived.formed_routes+",
                "--indirect-selection",
                "cautious",
            ),
            DBT_DIR,
        ),
    ]


def test_the_hourly_lane_defers_every_build_to_the_state_it_is_given_and_takes_no_parents():
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", state=Path("/m/target"))

    for run in runs[1:]:
        if run.argv[0] == "python":
            assert "--defer" not in run.argv, "a Python step reads the warehouse; it has nothing to defer"
            continue
        assert run.argv[-3:] == ("--defer", "--state", "/m/target"), run.argv
        assert not set(build_marts.LANE_PARENTS) & set(run.argv), run.argv
        assert "--indirect-selection" not in run.argv
    assert "--defer" not in runs[0].argv, "dbt seed loads files; it has nothing to defer"


def test_an_hourly_step_runs_in_the_hourly_lane_and_no_monthly_step_does():
    runs = plan([*PAIR, SQUARES], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly")

    assert [run.label for run in runs if run.argv[0] == "python"] == ["step_weather_squares"]
    stage_a, unblocked = runs[1].argv, runs[3].argv
    assert "source:derived+" in stage_a, "stage A leaves every derived table's descendants for after its step"
    assert unblocked[unblocked.index("-s") :] == (
        "-s",
        "source:derived.weather_squares+",
        "--exclude",
        "path:models/publish",
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
    writers = runs[-1].argv
    assert writers[writers.index("--exclude") :][:4] == (
        "--exclude",
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
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE, ("dbt", "seed")]
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
        plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True, lane="monthly", history=_history(tmp_path))
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


# --- The row history (build_marts.py's docstring, "THE ROW HISTORY IS RESTORED FIRST AND SAVED LAST") ---


def test_plan_with_a_history_store_restores_before_the_seeds_and_saves_after_the_writers():
    history = History("s3://bucket/history/monthly", False, "/venv/extract/bin/python")
    runs = plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, history=history)

    store = ("--url", "s3://bucket/history/monthly", "--warehouse", "/w/warehouse.duckdb")
    assert runs[0].argv == ("/venv/extract/bin/python", "row_history.py", "restore", *store)
    assert runs[1].argv[:2] == ("dbt", "seed")
    assert runs[-1].argv == ("/venv/extract/bin/python", "row_history.py", "save", *store)
    assert runs[-2].argv[-2:] == ("-s", "path:models/publish"), "the save waits for the writers"


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

    listed, quiet = build_marts.resolve_history(
        "s3://b/history/monthly", fixtures=False, cold_start=False, python="python", started=started
    )
    unlisted, warning = build_marts.resolve_history(
        "s3://b/history/conditions_ua", fixtures=False, cold_start=False, python="python", started=started
    )
    forced, _ = build_marts.resolve_history(
        "s3://b/history/monthly", fixtures=False, cold_start=True, python="python", started=started
    )

    assert not listed.cold_start and quiet is None
    assert unlisted.cold_start and warning.startswith("::warning") and "conditions_ua" in warning
    assert forced.cold_start


def test_row_history_stores_toml_lists_store_names_with_the_run_that_started_each():
    started = build_marts.started_history_stores()

    assert all("/" not in name and isinstance(run, str) and run for name, run in started.items())


def test_a_failed_restore_stops_the_build_before_dbt_by_default(monkeypatch, tmp_path):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={1: 1})

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [RESTORE]


def test_a_degraded_build_runs_every_dbt_command_without_snapshots_or_history_and_saves_nothing(monkeypatch, tmp_path):
    """The conditions legs (--history-on-failure degrade): publish with null dates, save nothing, exit DEGRADED_EXIT."""
    code, recorder = _main(
        monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={1: 2}, extra=("--history-on-failure", "degrade")
    )

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    after_restore = [(argv, cwd) for argv, cwd, _ in recorder.calls][1:]
    assert code == build_marts.DEGRADED_EXIT
    assert after_restore == argvs(plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True, snapshots=False))
    assert not [argv for argv, _, _ in recorder.calls if argv[2:3] == ("save",)], "a degraded build never saves"
    builds = [argv for argv, _, _ in recorder.calls if argv[:2] == ("dbt", "build")]
    writers = [argv for argv in builds if "-s" in argv and argv[argv.index("-s") + 1] == "path:models/publish"]
    assert len(writers) == 1 and all(build_marts.SNAPSHOTS in argv for argv in builds if argv not in writers)
    for _, _, env in recorder.calls[1:]:
        assert env["OURHIKE_ROW_HISTORY"] == "off", "macros/row_history.sql's row_history_mart() reads it"


def test_a_command_that_fails_with_the_degraded_exit_code_is_answered_as_a_plain_failure(monkeypatch, tmp_path):
    """publish-conditions.yml publishes on DEGRADED_EXIT, so only a build that did degrade may answer with it."""
    for extra in ((), ("--history-on-failure", "degrade")):
        code, _ = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={3: build_marts.DEGRADED_EXIT}, extra=extra)

        assert code == 1


def test_without_snapshots_every_build_but_the_writers_excludes_them():
    runs = plan([DEM_SAMPLING], dbt="dbt", python="python", paths=PATHS, fixtures=True, snapshots=False)

    builds = [run.argv for run in runs if run.argv[:2] == ("dbt", "build")]
    assert [build_marts.SNAPSHOTS in argv for argv in builds] == [True, True, False]


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
