"""CI's dbt job runs the Elementary checks a pull request reaches, and every one otherwise (decision 111).

The maintainer's poll of 2026-10-08: "Run all of them that have been modified, and downstream models." On a pull
request, pipeline-tests.yml's dbt job parses its base once more with Elementary's two switches on, and build_marts.py
runs `tag:elementary_check,state:modified+` against it (its docstring, "A PULL REQUEST RUNS THE CHECKS ITS CHANGE
REACHES"). What is held here is the half in the workflow and in scripts/test.sh:

- the base is parsed only on a pull request, in the contract step's worktree, with both switches and against the
  warehouse file the build uses, since that file's name is every node's database (a base parsed against another name
  read all 1,979 checks as changed, measured 2026-10-08 with `dbt ls` on dbt 2.0.6);
- a push to main, a merge-queue entry and a pull request whose base would not parse run every check, never none,
  and the log says which;
- scripts/test.sh passes its own base the same way, and `--all` runs every check, as a push to main does.

Both shell scripts run here with a stand-in for dbt and for python, so what they decide is checked, not only their
text.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pipeline-tests.yml"
TEST_SH = ROOT / "scripts" / "test.sh"
BUILD_STEP = "dbt build, the Python steps and the pub_ writers (build_marts.py)"
CONTRACT_STEP = "Contract versions against the base's manifest"


def _steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["dbt"]["steps"]


def _step(*, name: str | None = None, id_: str | None = None) -> dict:
    (step,) = [step for step in _steps() if (name and step.get("name") == name) or (id_ and step.get("id") == id_)]
    return step


def _stand_in(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)


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


# --- pipeline-tests.yml's dbt job -----------------------------------------------------------------------------------


def test_the_base_is_parsed_with_elementarys_checks_only_on_a_pull_request_in_the_contract_steps_worktree():
    step = _step(id_="checks-base")
    names = [each.get("name") for each in _steps()]

    assert step["if"] == "steps.scope.outputs.run == 'true' && github.event_name == 'pull_request'"
    assert names.index(CONTRACT_STEP) < names.index(step["name"]) < names.index(BUILD_STEP)
    assert 'base="$RUNNER_TEMP/contract-base"' in step["run"] and "$RUNNER_TEMP/contract-base" in _step(name=CONTRACT_STEP)["run"]
    assert "OURHIKE_ELEMENTARY=true OURHIKE_ELEMENTARY_CHECKS=true" in step["run"]


def test_the_base_is_parsed_against_the_warehouse_file_the_build_loads_and_builds_in():
    """The fixture load writes data/warehouse.duckdb under pipeline/, the build names no other, and build_marts.py's
    default is that file, so the base's database name is the build's."""
    parsed = re.search(r'OURHIKE_WAREHOUSE="\$GITHUB_WORKSPACE/pipeline/([^"]+)"', _step(id_="checks-base")["run"])
    loaded = [step["run"] for step in _steps() if "-m extract._fixtures" in str(step.get("run", ""))]

    assert parsed and parsed.group(1) == "data/warehouse.duckdb"
    assert len(loaded) == 1 and "--warehouse data/warehouse.duckdb" in loaded[0]
    assert "--warehouse" not in _step(name=BUILD_STEP)["run"] and "OURHIKE_WAREHOUSE" not in str(
        _step(name=BUILD_STEP).get("env")
    )


@pytest.mark.parametrize(
    ("case", "parses", "output"),
    [
        ("a base that parses", True, True),
        ("a base that would not parse", False, False),
        ("a base from before check_contract_versions.py", None, False),
    ],
)
def test_the_base_step_names_a_directory_only_for_a_base_that_parsed_and_never_fails_the_job(tmp_path, case, parses, output):
    runner_temp, bin_ = tmp_path / "runner", tmp_path / "bin"
    dbt_dir = runner_temp / "contract-base" / "pipeline" / "dbt"
    dbt_dir.mkdir(parents=True)
    bin_.mkdir()
    if parses is not None:
        (dbt_dir.parent / "check_contract_versions.py").write_text("", encoding="utf-8")
    seen = tmp_path / "dbt-saw.txt"
    _stand_in(
        bin_,
        "dbt",
        f'echo "$PWD $* $OURHIKE_ELEMENTARY $OURHIKE_ELEMENTARY_CHECKS $OURHIKE_WAREHOUSE" > "{seen}"\n'
        + ("exit 0\n" if parses else "exit 2\n"),
    )
    github_output = tmp_path / "github_output"
    github_output.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_}:{os.environ['PATH']}",
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_OUTPUT": str(github_output),
        "GITHUB_WORKSPACE": str(tmp_path / "workspace"),
    }

    done = _run(_step(id_="checks-base")["run"], env, tmp_path)

    assert done.returncode == 0, (case, done.stdout, done.stderr)
    assert (github_output.read_text(encoding="utf-8") == f"dir={dbt_dir}\n") is output, case
    if parses is None:
        assert not seen.exists() and "::notice title=Every Elementary check::" in done.stdout
    else:
        assert seen.read_text(encoding="utf-8").split() == [
            str(dbt_dir),
            "parse",
            "--profiles-dir",
            ".",
            "true",
            "true",
            f"{tmp_path}/workspace/pipeline/data/warehouse.duckdb",
        ]
    if parses is False:
        assert "::notice title=Every Elementary check::" in done.stdout and "(exit 2)" in done.stdout


@pytest.mark.parametrize(
    ("event", "checks_base", "passed", "notice"),
    [
        ("pull_request", "/base/pipeline/dbt", True, "what this pull request reaches"),
        ("pull_request", "", False, "No base manifest holding the checks"),
        ("push", "", False, "A push runs every check"),
        ("merge_group", "", False, "A merge_group runs every check"),
    ],
)
def test_the_build_takes_a_base_only_when_the_step_named_one_and_says_which_checks_run(
    tmp_path, event, checks_base, passed, notice
):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    seen = tmp_path / "python-saw.txt"
    _stand_in(bin_, "python", f'printf "%s\\n" "$@" > "{seen}"\n')
    step = _step(name=BUILD_STEP)
    assert step["env"] == {"CHECKS_BASE": "${{ steps.checks-base.outputs.dir }}", "EVENT": "${{ github.event_name }}"}
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "RUNNER_TEMP": "/runner", "CHECKS_BASE": checks_base, "EVENT": event}

    done = _run(step["run"], env, tmp_path)

    assert done.returncode == 0, done.stderr
    argv = seen.read_text(encoding="utf-8").splitlines()
    assert argv[:4] == ["build_marts.py", "--fixtures", "--python", "/runner/pipeline/bin/python"]
    assert argv[4:] == (["--checks-base", checks_base] if passed else [])
    assert notice in done.stdout and done.stdout.startswith("::notice title=")


# --- scripts/test.sh ------------------------------------------------------------------------------------------------


def _function() -> str:
    text = TEST_SH.read_text(encoding="utf-8")
    start = text.index("checks_base=()\nchecks_base_for_dbt_suite() {")
    return text[start : text.index("\n}\n", start) + 3]


def test_test_sh_gives_its_build_the_base_it_prepared_and_parses_it_as_ci_does():
    text = TEST_SH.read_text(encoding="utf-8")
    (build,) = [line for line in text.splitlines() if 'step "dbt build_marts"' in line]
    function = _function()

    assert build.rstrip().endswith('"${checks_base[@]}"') and '--warehouse "$dbt_tmp/warehouse.duckdb"' in build
    assert text.index("\n    checks_base_for_dbt_suite\n") < text.index('step "dbt build_marts"')
    assert "OURHIKE_ELEMENTARY=true" in function and "OURHIKE_ELEMENTARY_CHECKS=true" in function
    assert '"OURHIKE_WAREHOUSE=$dbt_tmp/warehouse.duckdb"' in function, "the build's own warehouse file, as in CI"
    assert 'checks_base=(--checks-base "$exported/pipeline/dbt")' in function


@pytest.mark.parametrize(
    ("run_all", "base", "said"),
    [
        ("true", "origin/main", "--all runs every check, as a push to main does"),
        ("false", "", "there is no merge base with a base branch to compare with"),
    ],
)
def test_test_sh_runs_every_check_under_all_and_with_no_base_and_says_so(tmp_path, run_all, base, said):
    script = f'{_function()}\nrun_all={run_all}\nbase="{base}"\ndbt_tmp="{tmp_path}"\nchecks_base_for_dbt_suite\necho "passed=${{#checks_base[@]}}"\n'

    done = _run(script, {}, tmp_path)

    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [f"-- dbt checks base: every Elementary check runs: {said}", "passed=0"]
