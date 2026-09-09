"""The User-Agent has one home, and this is what keeps it that way.

`lib/user_agent.py` exists because the same literal had been written out
seven times, with the measurement that makes it mandatory beside exactly one
of them (#1295). Consolidating it was a one-off edit; nothing about that edit
stops the eighth copy being typed next month, which is precisely how the
first seven arrived.

So the guard here is the one `test_fetch_cache_paths.py` uses for the
workflow's cache paths: assert the property, not the edit. A module that
spells the string itself fails this file by name, and the fix is one import.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from lib.user_agent import CONTACTABLE_USER_AGENT, PROJECT, REPO_URL, USER_AGENT, VERSION

PIPELINE_ROOT = Path(__file__).resolve().parent.parent

# Anything that looks like this project naming itself to a server. Matched on
# the project token rather than on either whole string, so a copy that drifts
# in its punctuation - the exact way the two existing forms differ - is caught
# too rather than sliding past a literal comparison.
SELF_NAMING = re.compile(r'["\']OurHike-pipeline/')

# Where the string is allowed to be spelled out. Two entries and no more: the
# module that owns it, and this file's own assertions about it.
ALLOWED = {"lib/user_agent.py", "tests/test_user_agent.py"}


def python_sources() -> list[Path]:
    return sorted(path for path in PIPELINE_ROOT.rglob("*.py") if "/data/" not in str(path) and ".venv" not in str(path))


def test_the_string_is_spelled_in_exactly_one_module():
    offenders = []
    for path in python_sources():
        rel = path.relative_to(PIPELINE_ROOT).as_posix()
        if rel in ALLOWED:
            continue
        if SELF_NAMING.search(path.read_text()):
            offenders.append(rel)

    assert not offenders, (
        "these modules spell the User-Agent themselves instead of importing it "
        f"from lib/user_agent.py: {offenders}. That is the eighth copy #1295 "
        "removed the first seven of - the string is load-bearing against ATC's "
        "host, and its measurement lives in lib/user_agent.py."
    )


@pytest.mark.parametrize(
    "agent",
    [USER_AGENT, CONTACTABLE_USER_AGENT],
    ids=["default", "contactable"],
)
def test_both_forms_name_the_project_and_link_to_it(agent: str):
    """An operator reading one line of their log can tell who this is."""
    assert agent.startswith(f"{PROJECT}/{VERSION}")
    assert REPO_URL in agent


def test_the_two_forms_are_different_and_only_in_the_contact_route():
    """Wikimedia wants a way to reach the operator; nobody else asks for one.

    Pinned because the difference is easy to read as an accident and tidy
    away - `fetch_poi_images.py:59-60` records that their etiquette page
    requires it.
    """
    assert USER_AGENT != CONTACTABLE_USER_AGENT
    assert "contact via repository issues" in CONTACTABLE_USER_AGENT
    assert "contact" not in USER_AGENT


def test_a_version_bump_moves_both_forms():
    """The actual win over seven copies, asserted rather than assumed."""
    assert VERSION in USER_AGENT
    assert VERSION in CONTACTABLE_USER_AGENT
