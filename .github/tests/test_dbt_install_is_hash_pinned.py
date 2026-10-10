"""Every install of pipeline/requirements-dbt.txt checks a sha256 for every file, and the file lists one for every pin.

Decision 144 (pipeline/ELT.md, the maintainer's poll of 2026-10-09): the page dbt writes for ourhike.org/data/
shares an origin with the app's signed-in session, and its scripts come from this install, so the install is
hash-pinned. It takes both halves below, because either one alone fails open:

- requirements-dbt.txt lists `--hash=sha256:` under every pin. pip switches hash checking on by itself only when
  a file lists some hash, so a recompile without --generate-hashes would install unchecked and say nothing.
- every step that installs the file passes --require-hashes, so a file that lost its hashes stops the install
  instead. Measured 2026-10-10 on pip 24.0: the same pins with no hashes and that flag failed with "Hashes are
  required in --require-hashes mode, but they are missing from some requirements", and one wrong hash failed with
  "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE".
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "pipeline" / "requirements-dbt.txt"
TEST_SH = ROOT / "scripts" / "test.sh"

#: A command that runs pip's install on the dbt requirements file, quoted venv paths included
#: (`"$RUNNER_TEMP/dbt/bin/pip" install`).
INSTALLS_DBT = re.compile(r"\bpip3?\"?\s+install\b[^\n]*\brequirements-dbt\.txt\b")

#: (file under .github, job id): every place that installs requirements-dbt.txt today. A composite action has no
#: job, so its id is None. A new install must join this list, so the test below checks it too, and a list the scan
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
    for where, job_id, step in _steps():
        for command in _commands(str(step.get("run", ""))):
            if INSTALLS_DBT.search(command):
                yield where, job_id, command


def _pins(text: str) -> list[str]:
    """Each requirement of a compiled file, its continuation lines joined, comments and options dropped."""
    lines = [line for line in _commands(text) if line.strip() and not line.lstrip().startswith(("#", "-"))]
    return [line.strip() for line in lines]


def test_every_pin_in_requirements_dbt_txt_lists_a_sha256():
    text = REQUIREMENTS.read_text(encoding="utf-8")
    pins = _pins(text)
    assert len(pins) >= 3, pins  # dbt, duckdb and sqlfluff at least, so a parse that finds nothing fails here
    unhashed = [pin for pin in pins if not re.search(r"--hash=sha256:[0-9a-f]{64}\b", pin)]
    unpinned = [pin for pin in pins if not re.match(r"^[A-Za-z0-9_.-]+==[^\s=;]+(\s|$)", pin)]
    assert unhashed == [], f"requirements-dbt.txt has pins with no sha256: {unhashed}"
    assert unpinned == [], f"--require-hashes refuses a requirement that is not pinned with ==: {unpinned}"


def test_the_header_records_a_compile_that_keeps_the_hashes():
    """The next recompile, by hand or by Dependabot, repeats the command the header records."""
    header = REQUIREMENTS.read_text(encoding="utf-8")[:400]
    (command,) = [line for line in header.splitlines() if "pip-compile" in line and "requirements-dbt.in" in line]
    assert "--generate-hashes" in command, command


def test_the_install_sites_listed_here_are_every_install_of_requirements_dbt_txt():
    found = {(where, job_id) for where, job_id, _command in _installs()}
    assert found == INSTALL_SITES


def test_every_install_of_requirements_dbt_txt_requires_hashes():
    missing = [
        f"{where}:{job_id}: {command.strip()}" for where, job_id, command in _installs() if "--require-hashes" not in command
    ]
    assert missing == []


def test_the_install_test_sh_prints_for_a_missing_dbt_requires_hashes_too():
    """scripts/test.sh installs nothing, but the commands it prints are the ones a session copies."""
    printed = [line for line in TEST_SH.read_text(encoding="utf-8").splitlines() if INSTALLS_DBT.search(line)]
    assert printed, "scripts/test.sh no longer prints how to install requirements-dbt.txt"
    assert all("--require-hashes" in line for line in printed), printed
