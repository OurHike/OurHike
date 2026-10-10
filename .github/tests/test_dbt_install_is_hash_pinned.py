"""Every install of pipeline/requirements-dbt.txt checks a sha256 for every file, the build's own requirement included.

Decision 144 (pipeline/ELT.md, the maintainer's poll of 2026-10-09): the page dbt writes for ourhike.org/data/
shares an origin with the app's signed-in session, and its scripts come from this install, so the install is
hash-pinned. It takes all three parts below, because each one alone fails open:

- requirements-dbt.txt lists `--hash=sha256:` under every pin. pip switches hash checking on by itself only when
  a file lists some hash, so a recompile without --generate-hashes would install unchecked and say nothing.
- every step that installs the file passes --require-hashes, so a file that lost its hashes stops the install
  instead. Measured 2026-10-10 on pip 24.0: the same pins with no hashes and that flag failed with "Hashes are
  required in --require-hashes mode, but they are missing from some requirements", and one wrong hash failed with
  "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE".
- the same step installs requirements-dbt-build.txt first, hash-checked, and builds dbt with --no-build-isolation.
  dbt's sdist builds with `packaging`, which pip otherwise fetches into the build's own environment with no pin
  and no hash, under --require-hashes too (requirements-dbt-build.in has the measurement).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "pipeline"
TEST_SH = ROOT / "scripts" / "test.sh"

#: Each hash-pinned file and the .in it is compiled from.
COMPILED = {
    "requirements-dbt.txt": "requirements-dbt.in",
    "requirements-dbt-build.txt": "requirements-dbt-build.in",
}

#: A command that runs pip's install on one of the two files, quoted venv paths included
#: (`"$RUNNER_TEMP/dbt/bin/pip" install`).
INSTALLS_DBT = re.compile(r"\bpip3?\"?\s+install\b[^\n]*\brequirements-dbt\.txt\b")
INSTALLS_BUILD = re.compile(r"\bpip3?\"?\s+install\b[^\n]*\brequirements-dbt-build\.txt\b")

#: (file under .github, job id): every place that installs requirements-dbt.txt today. A composite action has no
#: job, so its id is None. A new install must join this list, so the tests below check it too, and a list the scan
#: no longer matches fails rather than passing on nothing.
INSTALL_SITES = {
    ("workflows/pipeline-tests.yml", "dbt"),
    ("workflows/publish-conditions.yml", "publish"),
    ("workflows/check-conditions.yml", "check"),
    ("workflows/build-reference.yml", "build"),
    # pages.yml's and pr-preview.yml's `docs` jobs, which build the /data/ page.
    ("actions/dbt-docs-site/action.yml", None),
}


def _commands(script: str) -> list[str]:
    """One string per shell command line, a backslash continuation joined to the line it continues."""
    return re.sub(r"\\\n\s*", " ", script).splitlines()


def _steps():
    github = ROOT / ".github"
    for path in sorted((github / "workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_id, job in (workflow.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                yield path.relative_to(github).as_posix(), job_id, step
    for path in sorted((github / "actions").glob("*/action.yml")):
        action = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for step in (action.get("runs") or {}).get("steps") or []:
            yield path.relative_to(github).as_posix(), None, step


def _installs():
    """(where, job id, the step's command lines, the index of the one installing requirements-dbt.txt)."""
    for where, job_id, step in _steps():
        commands = _commands(str(step.get("run", "")))
        for index, command in enumerate(commands):
            if INSTALLS_DBT.search(command):
                yield where, job_id, commands, index


def _builds_with_the_pinned_requirement(commands: list[str], index: int) -> list[str]:
    """What is wrong with how commands[index] builds dbt: nothing, when the build requirement went in first."""
    problems = []
    if "--no-build-isolation" not in commands[index]:
        problems.append("builds dbt in an isolated environment, which pip fills with no hash")
    earlier = [command for command in commands[:index] if INSTALLS_BUILD.search(command)]
    if not earlier or not all("--require-hashes" in command for command in earlier):
        problems.append("does not install requirements-dbt-build.txt with --require-hashes before it")
    return problems


def _pins(text: str) -> list[str]:
    """Each requirement of a compiled file, its continuation lines joined, comments and options dropped."""
    lines = [line for line in _commands(text) if line.strip() and not line.lstrip().startswith(("#", "-"))]
    return [line.strip() for line in lines]


@pytest.mark.parametrize("name", sorted(COMPILED))
def test_every_pin_lists_a_sha256(name):
    pins = _pins((PIPELINE / name).read_text(encoding="utf-8"))
    assert pins, f"{name}: no requirement found, so nothing below would be checked"
    unhashed = [pin for pin in pins if not re.search(r"--hash=sha256:[0-9a-f]{64}\b", pin)]
    unpinned = [pin for pin in pins if not re.match(r"^[A-Za-z0-9_.-]+==[^\s=;]+(\s|$)", pin)]
    assert unhashed == [], f"{name} has pins with no sha256: {unhashed}"
    assert unpinned == [], f"--require-hashes refuses a requirement that is not pinned with ==: {unpinned}"


def test_requirements_dbt_txt_still_holds_dbt():
    pins = _pins((PIPELINE / "requirements-dbt.txt").read_text(encoding="utf-8"))
    assert any(pin.startswith("dbt==") for pin in pins), pins


@pytest.mark.parametrize(("name", "source"), sorted(COMPILED.items()))
def test_the_header_records_a_compile_that_keeps_the_hashes(name, source):
    """The next recompile, by hand or by Dependabot, repeats the command the header records."""
    header = (PIPELINE / name).read_text(encoding="utf-8")[:400]
    commands = [line for line in header.splitlines() if "pip-compile" in line and source in line]
    assert len(commands) == 1, f"{name}'s header does not record the one pip-compile command that made it: {header!r}"
    assert "--generate-hashes" in commands[0], commands[0]


def test_the_install_sites_listed_here_are_every_install_of_requirements_dbt_txt():
    found = {(where, job_id) for where, job_id, _commands, _index in _installs()}
    assert found == INSTALL_SITES


def test_every_install_of_requirements_dbt_txt_requires_hashes():
    missing = [
        f"{where}:{job_id}: {commands[index].strip()}"
        for where, job_id, commands, index in _installs()
        if "--require-hashes" not in commands[index]
    ]
    assert missing == []


def test_every_install_builds_dbt_with_the_hash_checked_build_requirement():
    problems = [
        f"{where}:{job_id}: {problem}"
        for where, job_id, commands, index in _installs()
        for problem in _builds_with_the_pinned_requirement(commands, index)
    ]
    assert problems == []


def test_the_install_test_sh_prints_for_a_missing_dbt_is_the_same_two_steps():
    """scripts/test.sh installs nothing, but the commands it prints are the ones a session copies."""
    printed = [line for line in TEST_SH.read_text(encoding="utf-8").splitlines() if "pip install" in line]
    (index,) = [index for index, line in enumerate(printed) if INSTALLS_DBT.search(line)]
    assert "--require-hashes" in printed[index], printed[index]
    assert _builds_with_the_pinned_requirement(printed, index) == []
