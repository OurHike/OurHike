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

import pytest
import yaml

import build_marts
from build_marts import STEPS, Paths, Step, derived_source_problems, plan

PIPELINE_DIR = Path(build_marts.__file__).resolve().parent
DBT_DIR = PIPELINE_DIR / "dbt"
REPO_DIR = PIPELINE_DIR.parent
PATHS = Paths(warehouse=Path("/w/warehouse.duckdb"), processed_dir=Path("/w/processed"), raw_dir=Path("/w/raw"))
DEM_SAMPLING = STEPS[0]
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

    for flag in (argument for argument in step.command[1:] + step.fixture_args if argument.startswith("--")):
        assert re.search(rf"(^|\s|\[){re.escape(flag)}\b", help_text), f"{step.command[0]} --help names no {flag}"


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
            *extra,
        ]
    )
    return code, recorder


def test_main_runs_the_plan_in_order_with_one_warehouse_for_dbt_and_the_steps(monkeypatch, tmp_path):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES))

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    assert code == 0
    assert [(argv, cwd) for argv, cwd, _ in recorder.calls] == argvs(
        plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True)
    )
    for _, _, env in recorder.calls:
        assert env["OURHIKE_WAREHOUSE"] == str(tmp_path / "warehouse.duckdb")
        assert env["OURHIKE_PROCESSED_DIR"] == str(tmp_path / "processed")
    assert (tmp_path / "processed").is_dir(), "COPY creates no directory, so the writers' folder must exist first"


def test_main_stops_at_the_first_command_that_fails_and_answers_with_its_exit_code(monkeypatch, tmp_path):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES), codes={2: 2})

    assert code == 2
    assert [argv[:2] for argv, _, _ in recorder.calls] == [("dbt", "seed"), ("dbt", "build")]


def test_main_refuses_after_the_seeds_when_a_derived_source_has_no_step(monkeypatch, tmp_path, capsys):
    code, recorder = _main(monkeypatch, tmp_path, _manifest(*STEP_TABLES, "graph_pieces"))

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [("dbt", "seed")]
    assert "source derived.graph_pieces is declared and no entry of build_marts.STEPS writes it" in capsys.readouterr().out


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
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="monthly")
    everything = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False)

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


def test_the_hourly_lane_is_the_seeds_its_own_nodes_and_its_own_writers_and_no_python_step():
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly")

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
                "--exclude",
                "package:dbt_project_evaluator",
                "path:models/publish",
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
            ),
            DBT_DIR,
        ),
    ]


def test_the_hourly_lane_defers_both_builds_to_the_state_it_is_given():
    runs = plan(STEPS, dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="hourly", state=Path("/m/target"))

    for run in runs[1:]:
        assert run.argv[-3:] == ("--defer", "--state", "/m/target"), run.argv
    assert "--defer" not in runs[0].argv, "dbt seed loads files; it has nothing to defer"


@pytest.mark.parametrize("lane", [None, "monthly"])
def test_state_outside_the_hourly_lane_is_refused_because_nothing_else_defers(lane):
    with pytest.raises(ValueError, match="hourly lane's"):
        plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane=lane, state=Path("/m/target"))


def test_a_lane_this_file_does_not_know_is_refused():
    with pytest.raises(ValueError, match="no lane 'weekly'"):
        plan([], dbt="dbt", python="python", paths=PATHS, fixtures=False, lane="weekly")


def _lane_manifest(step_reads: dict[str, list[str]]) -> dict:
    """Two sources, hourly and monthly, each feeding one model, and one step exposure per entry of step_reads."""
    manifest = _manifest(*STEP_TABLES)
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
    manifest = _lane_manifest({step.name: ["model.ourhike.int_elevation__sample_points"] for step in STEPS})

    for lane in build_marts.LANES:
        assert build_marts.lane_problems(manifest, STEPS, lane) == []


@pytest.mark.parametrize("lane", ["monthly", "hourly"])
@pytest.mark.parametrize("node", ["model.ourhike.closures", "model.ourhike.int_warnings__terms"])
def test_a_lane_refuses_a_step_that_reads_a_node_an_hourly_or_daily_source_reaches(lane, node):
    manifest = _lane_manifest({DEM_SAMPLING.name: [node], **{step.name: [] for step in STEPS[1:]}})

    problems = build_marts.lane_problems(manifest, STEPS, lane)

    assert problems == [
        f"{DEM_SAMPLING.name} reads {node}, which an hourly or daily source reaches: the monthly lane does not build "
        "it, and the hourly lane runs no step, so the step's answer would go stale under it"
    ]


def test_a_lane_refuses_a_step_with_no_exposure_naming_its_inputs_and_no_lane_does_not_ask():
    manifest = _lane_manifest({})

    assert build_marts.lane_problems(manifest, [DEM_SAMPLING], "monthly") == [
        f"{DEM_SAMPLING.name} has no exposure named {DEM_SAMPLING.name} listing what it reads, so the monthly lane "
        "cannot check that it builds the step's inputs"
    ]
    assert build_marts.lane_problems(manifest, [DEM_SAMPLING], None) == []


def test_main_refuses_after_the_seeds_when_the_monthly_lane_would_leave_a_steps_input_unbuilt(monkeypatch, tmp_path, capsys):
    manifest = _lane_manifest({DEM_SAMPLING.name: ["model.ourhike.closures"], **{step.name: [] for step in STEPS[1:]}})

    code, recorder = _main(monkeypatch, tmp_path, manifest, extra=("--lane", "monthly"))

    assert code == 1
    assert [argv[:2] for argv, _, _ in recorder.calls] == [("dbt", "seed")]
    assert f"{DEM_SAMPLING.name} reads model.ourhike.closures" in capsys.readouterr().out


def test_main_runs_the_monthly_lanes_plan_when_every_step_reads_monthly_nodes(monkeypatch, tmp_path):
    manifest = _lane_manifest({step.name: ["model.ourhike.int_elevation__sample_points"] for step in STEPS})

    code, recorder = _main(monkeypatch, tmp_path, manifest, extra=("--lane", "monthly"))

    tmp_path = tmp_path.resolve()
    paths = Paths(tmp_path / "warehouse.duckdb", tmp_path / "processed", tmp_path / "raw")
    assert code == 0
    assert [(argv, cwd) for argv, cwd, _ in recorder.calls] == argvs(
        plan(STEPS, dbt="dbt", python="python", paths=paths, fixtures=True, lane="monthly")
    )


def test_every_step_names_what_it_reads_in_an_exposure_of_its_own_name():
    """The lanes' check reads each step's inputs off its step_<name> exposure, so a step without one refuses every lane build."""
    exposures = {}
    for path in sorted((DBT_DIR / "models").rglob("*.yml")):
        for exposure in yaml.safe_load(path.read_text()).get("exposures") or []:
            exposures[exposure["name"]] = exposure

    for step in STEPS:
        assert step.name in exposures, f"no exposure named {step.name} lists what {step.command[0]} reads"
        assert exposures[step.name].get("depends_on"), f"exposure {step.name} names no input"
