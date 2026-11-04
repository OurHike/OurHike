"""How the hash-pin tests read a compiled requirements file and the installs of it, written once.

test_archive_install_is_hash_pinned.py, test_extract_install_is_hash_pinned.py and test_dbt_install_is_hash_pinned.py
each check that a compiled file lists a sha256 under every pin and that every install of it passes --require-hashes.
They held three copies of `commands` and read a compiled file two different ways, so a fix to either parse had to be
made more than once. Not a test module: pytest collects only `test_*.py`, so it runs nothing here.
"""

from __future__ import annotations

import re
from pathlib import Path

GITHUB = Path(__file__).resolve().parents[1]


def commands(text: str) -> list[str]:
    """One string per shell command line, a backslash continuation joined to the line it continues."""
    return re.sub(r"\\\n\s*", " ", text).splitlines()


def installs_of(pattern: re.Pattern[str]) -> dict[str, list[str]]:
    """Each workflow and composite action under .github whose command lines `pattern` finds, with those lines."""
    found: dict[str, list[str]] = {}
    for path in sorted([*GITHUB.glob("workflows/*.yml"), *GITHUB.glob("actions/*/action.yml")]):
        matched = [command for command in commands(path.read_text(encoding="utf-8")) if pattern.search(command)]
        if matched:
            found[str(path.relative_to(GITHUB))] = matched
    return found


def pins(text: str) -> list[str]:
    """Each requirement of a compiled file, its continuation lines joined, comments and options dropped."""
    return [line.strip() for line in commands(text) if line.strip() and not line.lstrip().startswith(("#", "-"))]
