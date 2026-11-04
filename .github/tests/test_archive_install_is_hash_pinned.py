"""Every install of backend/requirements-archive.txt checks a sha256 for every file.

The 2026-11-04 security review: analytics-rollup.yml's `ua` and `production` jobs install this file, and the packages it
installs are imported by the steps that hold the usage archive's R2 write keys and the analytics databases' URLs
(`scripts/analytics_archive.py`, `analytics_rollup.py`, `analytics_quality.py`). It carried `==` pins and no hashes,
while the pipeline's dbt and extract installs, which run beside keys of the same kind, are hash-pinned
(test_dbt_install_is_hash_pinned.py, test_extract_install_is_hash_pinned.py). It takes both parts below, because
either alone fails open (test_dbt_install_is_hash_pinned.py has the measurement, on pip 24.0):

- requirements-archive.txt lists `--hash=sha256:` under every pin, compiled with --generate-hashes. pip switches hash
  checking on by itself only when a file lists some hash, so a recompile without the flag would install unchecked.
- every step that installs the file passes --require-hashes, so a file that lost its hashes stops the install instead.

No build environment to pin, as for the extract: `pip download --require-hashes --only-binary=:all:` for CPython 3.14
on manylinux x86_64, the jobs' interpreter, fetched a wheel for each of the 42 pins whose markers apply there and built
nothing from an sdist (measured 2026-11-04 with pip 24.0; colorama and tzdata are Windows-only).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "backend" / "requirements-archive.txt"

#: A command that runs pip's install on the file, quoted venv paths included.
INSTALLS_ARCHIVE = re.compile(r"\bpip3?\"?\s+install\b[^\n]*\brequirements-archive\.txt\b")

#: Every file under .github that installs requirements-archive.txt today, with how many times. A new install must join
#: this list, so a scan that stops matching fails rather than passing on nothing.
INSTALL_SITES = {
    # The `ua` and `production` jobs, one install each.
    "workflows/analytics-rollup.yml": 2,
}


def _commands(text: str) -> list[str]:
    """One string per shell command line, a backslash continuation joined to the line it continues."""
    return re.sub(r"\\\n\s*", " ", text).splitlines()


def _installs() -> dict[str, list[str]]:
    github = ROOT / ".github"
    found: dict[str, list[str]] = {}
    for path in sorted([*github.glob("workflows/*.yml"), *github.glob("actions/*/action.yml")]):
        commands = [command for command in _commands(path.read_text(encoding="utf-8")) if INSTALLS_ARCHIVE.search(command)]
        if commands:
            found[str(path.relative_to(github))] = commands
    return found


def _pins(text: str) -> list[str]:
    """Each requirement of the compiled file, its continuation lines joined, comments and options dropped."""
    lines = [line for line in _commands(text) if line.strip() and not line.lstrip().startswith(("#", "-"))]
    return [line.strip() for line in lines]


def test_every_pin_in_requirements_archive_lists_a_sha256():
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "--generate-hashes" in text.splitlines()[1], "the header's own command compiles with --generate-hashes"
    pins = _pins(text)
    assert len(pins) >= 40, "the file's pins were found"
    assert any(pin.startswith("pyarrow==") for pin in pins), "the one package only the archive needs is still in it"
    unhashed = [pin.split()[0] for pin in pins if not re.search(r"--hash=sha256:[0-9a-f]{64}\b", pin)]
    unpinned = [pin.split()[0] for pin in pins if not re.match(r"^[A-Za-z0-9_.-]+==[^\s=;]+(\s|$)", pin)]
    assert unhashed == []
    assert unpinned == [], "--require-hashes refuses a requirement that is not pinned with =="


def test_every_install_of_requirements_archive_requires_hashes():
    installs = _installs()
    assert {site: len(commands) for site, commands in installs.items()} == INSTALL_SITES
    missing = [
        (site, command.strip())
        for site, commands in installs.items()
        for command in commands
        if "--require-hashes" not in command
    ]
    assert missing == []
