"""CI's dbt job builds a pull request from main's last build when it safely can, and everything otherwise.

The maintainer's poll of 2026-10-15 ("In this PR anyway"): the build step took 16 min 7 s on 2a826f01 (Pipeline tests
run 38773605297), on every pull request. pipeline/state_base.py's docstring has the design; what is held here is the
workflow's half and the rules' answers:

- a push to main keeps its build (the warehouse and the manifest it was built with) and saves it to the Actions cache
  under its commit, right after a build that passed; a pull request and a merge-queue entry never do;
- a pull request, and nothing else, restores one: its base commit's, else the newest by prefix;
- the decision runs the rules (state_base.RULES) over what changed, on sample path lists below, and anything it cannot
  answer is a full build said in one `::notice`, never a red job. The step's own command runs here over a scratch git
  repository, so what it decides is checked, not only its text;
- the build step passes --state-base only when the decision named a directory.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pipeline-tests.yml"
STATE_BASE = ROOT / "pipeline" / "state_base.py"
BUILD_STEP = "dbt build, the Python steps and the pub_ writers (build_marts.py)"
LOAD_STEP = "Load the warehouse through the extract (fixture mode)"
KEEP, SAVE = "Keep this build for pull requests (push to main)", "Save this build for pull requests (push to main)"
RESTORE, DECIDE = (
    "Restore main's last build, for a state build (pull requests)",
    "A state build or the full build (pull requests)",
)
SCOPED = "steps.scope.outputs.run == 'true'"


def _state_base():
    spec = importlib.util.spec_from_file_location("state_base", STATE_BASE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


state_base = _state_base()


def _steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["dbt"]["steps"]


def _step(name: str) -> dict:
    (step,) = [step for step in _steps() if step.get("name") == name]
    return step


def _names() -> list[str]:
    return [step.get("name") for step in _steps()]


def _run(script: str, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    """`script` as a `run:` step runs it: bash with -e and pipefail."""
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        cwd=cwd,
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True,
        text=True,
        check=False,
    )


# --- main keeps its build ------------------------------------------------------------------------------------------


def test_only_a_push_to_main_whose_build_passed_keeps_the_build_and_right_after_it():
    """Right after: the evaluator step builds into the warehouse and every later dbt command rewrites the manifest."""
    keep, save, names = _step(KEEP), _step(SAVE), _names()

    assert names.index(BUILD_STEP) + 1 == names.index(KEEP) and names.index(KEEP) + 1 == names.index(SAVE)
    assert _step(BUILD_STEP)["id"] == "build"
    assert keep["if"] == (
        f"{SCOPED} && github.event_name == 'push' && github.ref == 'refs/heads/main' && steps.build.outcome == 'success'"
    )
    assert "pull_request" not in keep["if"] and "merge_group" not in keep["if"]
    assert keep["run"].split("\n")[2:4] == [
        'cp data/warehouse.duckdb "$kept/warehouse.duckdb"',
        'cp dbt/target/manifest.json "$kept/target/manifest.json"',
    ]
    assert save["if"] == "always() && steps.state-keep.outcome == 'success'" and keep["id"] == "state-keep"
    assert save["uses"].startswith("actions/cache/save@") and save["continue-on-error"] is True


def test_the_save_is_keyed_by_the_commit_the_decision_reads_back():
    save = _step(SAVE)["with"]

    assert save == {"path": "${{ runner.temp }}/dbt-ci-base", "key": f"{state_base.KEY_PREFIX}${{{{ github.sha }}}}"}
    assert state_base.commit_of(state_base.KEY_PREFIX + "a" * 40) == "a" * 40


def test_the_keep_step_copies_what_the_decision_looks_for(tmp_path):
    pipeline = tmp_path / "pipeline"
    (pipeline / "data").mkdir(parents=True)
    (pipeline / "dbt" / "target").mkdir(parents=True)
    (pipeline / "data" / "warehouse.duckdb").write_bytes(b"warehouse")
    (pipeline / "dbt" / "target" / "manifest.json").write_text("{}")

    done = _run(_step(KEEP)["run"], {"RUNNER_TEMP": str(tmp_path / "runner")}, pipeline)

    kept = tmp_path / "runner" / "dbt-ci-base"
    assert done.returncode == 0, done.stderr
    assert (kept / state_base.WAREHOUSE_NAME).read_bytes() == b"warehouse"
    assert (kept / state_base.MANIFEST_IN_BASE).read_text() == "{}"


# --- a pull request restores it ------------------------------------------------------------------------------------


def test_only_a_pull_request_restores_main_s_build_its_base_commit_s_first_then_the_newest():
    restore, decide, names = _step(RESTORE), _step(DECIDE), _names()

    for step in (restore, decide):
        assert step["if"] == f"{SCOPED} && github.event_name == 'pull_request'"
    assert restore["uses"].startswith("actions/cache/restore@") and restore["id"] == "state-cache"
    assert restore["with"] == {
        "path": "${{ runner.temp }}/dbt-ci-base",
        "key": f"{state_base.KEY_PREFIX}${{{{ github.event.pull_request.base.sha }}}}",
        "restore-keys": state_base.KEY_PREFIX,
    }
    # After `dbt parse` wrote the head manifest the decision compares macros with, before the load writes the
    # warehouse the decision may have put in place.
    assert names.index("dbt parse") < names.index(RESTORE) < names.index(DECIDE) < names.index(LOAD_STEP)
    assert decide["env"] == {"MATCHED_KEY": "${{ steps.state-cache.outputs.cache-matched-key }}"}


def test_the_decision_moves_the_warehouse_to_the_one_the_load_and_the_build_use():
    decide = " ".join(_step(DECIDE)["run"].split())

    assert "--warehouse data/warehouse.duckdb" in decide and "--head-manifest dbt/target/manifest.json" in decide
    assert "--warehouse data/warehouse.duckdb" in " ".join(_step(LOAD_STEP)["run"].split())
    assert "--warehouse" not in _step(BUILD_STEP)["run"], "build_marts.py's default is data/warehouse.duckdb"


@pytest.mark.parametrize(
    ("event", "state", "passed", "notice"),
    [
        ("pull_request", "/runner/dbt-ci-base/target", True, None),
        ("pull_request", "", False, None),
        ("push", "", False, "A push builds every node"),
        ("merge_group", "", False, "A merge_group builds every node"),
    ],
)
def test_the_build_takes_a_state_base_only_when_the_decision_named_one(tmp_path, event, state, passed, notice):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    seen = tmp_path / "python-saw.txt"
    (bin_ / "python").write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{seen}"\n')
    (bin_ / "python").chmod(0o755)
    step = _step(BUILD_STEP)
    assert step["env"]["STATE_BASE"] == "${{ steps.state.outputs.dir }}" and _step(DECIDE)["id"] == "state"
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "RUNNER_TEMP": "/runner", "CHECKS_BASE": "", "STATE_BASE": state}

    done = _run(step["run"], {**env, "EVENT": event}, tmp_path)

    assert done.returncode == 0, done.stderr
    argv = seen.read_text(encoding="utf-8").splitlines()
    assert argv[4:] == (["--state-base", state] if passed else [])
    assert ("::notice title=Full fixture build::" in done.stdout) is (notice is not None)
    if notice:
        assert notice in done.stdout


# --- the rules ------------------------------------------------------------------------------------------------------

STATE_PATHS = [
    "pipeline/dbt/models/staging/atc/stg_atc__shelters.sql",
    "pipeline/dbt/models/marts/closures/_closures__models.yml",
    "pipeline/dbt/models/intermediate/points_of_interest/int_points_of_interest__unioned.sql",
    "pipeline/dbt/seeds/notice_words.csv",
    "pipeline/dbt/seeds/_seeds.yml",
    "pipeline/dbt/snapshots/closures/int_closures__history.sql",
    "pipeline/dbt/tests/assert_pois_land_in_the_region_this_build_covers.sql",
    "pipeline/tests/test_build_marts.py",
    "pipeline/ELT.md",
    "client/src/App.tsx",
    "backend/app/main.py",
    ".github/workflows/pages.yml",
    ".github/tests/test_dbt_state_build.py",
    ".claude/skills/dbt/SKILL.md",
    "README.md",
]
FULL_PATHS = {
    "pipeline/dbt/tests/generic/equal_rowcount_to_raw.sql": "a generic test",
    "pipeline/dbt/macros/row_history.sql": "how dbt runs",
    "pipeline/dbt/dbt_project.yml": "how dbt runs",
    "pipeline/dbt/packages.yml": "how dbt runs",
    "pipeline/dbt/package-lock.yml": "how dbt runs",
    "pipeline/dbt/profiles.yml": "how dbt runs",
    "pipeline/make_dbt_fixtures.py": "the raw tables",
    "pipeline/extract/atc/points_of_interest.py": "the raw tables",
    "pipeline/extract/atc/NOTES.md": "the raw tables",
    "pipeline/sources.json": "the raw tables",
    "pipeline/reference/atc_updates.json": "the raw tables",
    "pipeline/generate_dbt.py": "the generated models",
    "pipeline/make_dbt_staging.py": "the generated models",
    "pipeline/build_marts.py": "a Python step",
    "pipeline/step_node_lines.py": "a Python step",
    "pipeline/state_base.py": "a Python step",
    "pipeline/requirements-dbt.txt": "how dbt runs",
    ".github/workflows/pipeline-tests.yml": "the workflow that runs the build",
    ".github/actions/changed-paths/action.yml": "an action the workflow runs",
}


@pytest.mark.parametrize("path", STATE_PATHS)
def test_a_path_dbt_s_state_comparison_sees_or_no_build_reads_goes_through(path):
    assert state_base.verdict(path)[0] == state_base.STATE


@pytest.mark.parametrize(("path", "why"), FULL_PATHS.items())
def test_a_path_that_can_change_what_no_checksum_holds_forces_the_full_build(path, why):
    answer, reason = state_base.verdict(path)

    assert answer == state_base.FULL and why in reason


def test_one_path_the_rules_stop_is_enough_and_the_reason_names_it():
    assert state_base.path_problems(STATE_PATHS) == []
    assert state_base.path_problems([]) == []
    (problem,) = state_base.path_problems([*STATE_PATHS, "pipeline/sources.json"])
    assert problem.startswith("pipeline/sources.json changed: it can change the raw tables")


def test_every_path_the_dbt_job_reads_outside_pipeline_forces_the_full_build():
    """The dbt job's scope list is the tested statement of what its build reads (tests/test_build_marts.py and
    tests/test_extract_layout.py hold it to the imports), so the rule that lets the rest of the repository through
    cannot let through anything on it."""
    scope = next(step for step in _steps() if step.get("id") == "scope")["with"]["paths"].split()
    outside = [path for path in scope if not path.startswith("pipeline/")]

    assert outside, "the dbt job's scope list names its own workflow and action"
    for path in outside:
        assert state_base.verdict(path + ("action.yml" if path.endswith("/") else ""))[0] == state_base.FULL, path


def test_macros_are_compared_by_text_and_a_manifest_without_any_is_no_answer():
    head = {"macros": {"macro.ourhike.row_hash": {"macro_sql": "md5(x)"}, "macro.dbt_utils.x": {"macro_sql": "y"}}}

    assert state_base.macro_problems(head, json.loads(json.dumps(head))) == []
    (changed,) = state_base.macro_problems(head, {"macros": {**head["macros"], "macro.ourhike.row_hash": {"macro_sql": "old"}}})
    assert changed.startswith("1 macro(s) differ from the cached build's (macro.ourhike.row_hash)")
    (added,) = state_base.macro_problems(head, {"macros": {"macro.ourhike.row_hash": {"macro_sql": "md5(x)"}}})
    assert "macro.dbt_utils.x" in added
    assert "holds no macro" in state_base.macro_problems(head, {})[0]


# --- the decision, end to end ---------------------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


MANIFEST = {"macros": {"macro.ourhike.row_hash": {"macro_sql": "md5(x)"}}}


def _repository(tmp_path: Path, changed: dict[str, str], cached_macros: dict | None = None) -> tuple[Path, str, Path]:
    """A scratch repository whose first commit is main's cached build and whose HEAD changes `changed`, with this
    checkout's state_base.py, a head manifest, and the cache restored: (pipeline dir, cached commit, runner temp)."""
    repo = tmp_path / "repo"
    pipeline = repo / "pipeline"
    (pipeline / "dbt" / "models").mkdir(parents=True)
    (pipeline / "state_base.py").write_bytes(STATE_BASE.read_bytes())
    (pipeline / "dbt" / "models" / "stg_a.sql").write_text("select 1\n")
    _git(repo.parent, "init", "-q", str(repo))
    for setting in (("user.email", "ci@example.invalid"), ("user.name", "CI")):
        _git(repo, "config", *setting)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main")
    cached = _git(repo, "rev-parse", "HEAD")
    for path, text in changed.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "pull request")
    (pipeline / "dbt" / "target").mkdir(parents=True)
    (pipeline / "dbt" / "target" / "manifest.json").write_text(json.dumps(MANIFEST))
    runner = tmp_path / "runner"
    (runner / "dbt-ci-base" / "target").mkdir(parents=True)
    (runner / "dbt-ci-base" / "warehouse.duckdb").write_bytes(b"main's warehouse")
    (runner / "dbt-ci-base" / "target" / "manifest.json").write_text(json.dumps(cached_macros or MANIFEST))
    return pipeline, cached, runner


def _decide(pipeline: Path, matched_key: str, runner: Path) -> tuple[subprocess.CompletedProcess, str]:
    bin_ = runner / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "python").symlink_to(sys.executable)
    output = runner / "github_output"
    output.write_text("")
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "MATCHED_KEY": matched_key, "RUNNER_TEMP": str(runner)}
    done = _run(_step(DECIDE)["run"], {**env, "GITHUB_OUTPUT": str(output)}, pipeline)
    return done, output.read_text()


def test_a_change_dbt_s_state_comparison_sees_builds_by_state_from_main_s_warehouse(tmp_path):
    pipeline, cached, runner = _repository(tmp_path, {"pipeline/dbt/models/stg_a.sql": "-- a comment\nselect 1\n"})

    done, output = _decide(pipeline, state_base.KEY_PREFIX + cached, runner)

    assert done.returncode == 0, done.stderr
    assert output == f"dir={runner / 'dbt-ci-base' / 'target'}\n"
    assert (pipeline / "data" / "warehouse.duckdb").read_bytes() == b"main's warehouse"
    assert "::notice title=State build::" in done.stdout
    assert "-- state_base: state  pipeline/dbt/models/stg_a.sql" in done.stdout


@pytest.mark.parametrize(
    ("case", "why"),
    [
        ("no cache entry", "no build of main is cached"),
        ("a key with no commit", "names no commit"),
        ("a commit that cannot be fetched", "could not be fetched"),
        ("a path the rules stop", "pipeline/sources.json changed: it can change the raw tables"),
        ("a macro that differs", "1 macro(s) differ from the cached build's (macro.ourhike.row_hash)"),
        ("no cached manifest", "lacks target/manifest.json"),
    ],
)
def test_whatever_the_decision_cannot_answer_is_the_full_build_said_once_and_never_a_failure(tmp_path, case, why):
    changed = {"pipeline/dbt/models/stg_a.sql": "-- a comment\nselect 1\n"}
    if case == "a path the rules stop":
        changed["pipeline/sources.json"] = "[]\n"
    cached_macros = {"macros": {"macro.ourhike.row_hash": {"macro_sql": "older"}}} if case == "a macro that differs" else None
    pipeline, cached, runner = _repository(tmp_path, changed, cached_macros)
    key = {
        "no cache entry": "",
        "a key with no commit": "dbt-ci-base-main",
        "a commit that cannot be fetched": state_base.KEY_PREFIX + "0" * 40,
    }.get(case, state_base.KEY_PREFIX + cached)
    if case == "no cached manifest":
        (runner / "dbt-ci-base" / "target" / "manifest.json").unlink()

    done, output = _decide(pipeline, key, runner)

    assert done.returncode == 0, done.stderr
    assert output == "", "no `dir=`, so the build step passes no --state-base"
    assert not (pipeline / "data" / "warehouse.duckdb").exists(), "the load starts a warehouse of its own, as before"
    (notice,) = [line for line in done.stdout.splitlines() if line.startswith("::")]
    assert notice.startswith("::notice title=Full fixture build::Every node is built, as before decision 210: ") and why in notice


def test_a_decision_that_raises_is_a_full_build(monkeypatch, tmp_path, capsys):
    def broken(*_):
        raise OSError("disk gone")

    monkeypatch.setattr(state_base, "decide", broken)
    output = tmp_path / "github_output"
    output.write_text("")

    code = state_base.main(
        ["--base-dir", str(tmp_path), "--head-manifest", str(tmp_path / "m.json"), "--warehouse", str(tmp_path / "w")]
        + ["--github-output", str(output)]
    )

    assert code == 0 and output.read_text() == ""
    assert "::notice title=Full fixture build::Every node is built, as before decision 210: the decision itself failed" in (
        capsys.readouterr().out
    )
