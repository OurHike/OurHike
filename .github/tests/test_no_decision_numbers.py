"""No code, comment, test or doc points a reader at a numbered decision ("decision 204"): it states the choice.

pipeline/ELT.md once kept a numbered table of decisions, and the code cited rows of it by number. A number
tells a reader nothing until they open the table, and the table is gone: the maintainer asked (2026-10-16) for
every "decision N" to become the choice itself, said where it applies. These tests keep it that way.

What counts: "decision" or "decisions" (any case) followed by a number of up to three digits, also when a
comment wraps between the two ("decision\\n#: 194"). A date is not a number here, so "the maintainer's
decision 2026-09-09" passes. A file whose own sections are numbered decisions, or that cites another
document's or issue's numbered decisions, is listed in ALLOWED with why.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

DECISION_NUMBER = re.compile(r"\bdecisions?(?:\s|#:?|//|--|\*|\")+\d{1,3}[a-z]?\b(?!-\d)", re.IGNORECASE)

#: Files whose numbered decisions are their own or another document's, not ELT.md's retired table.
ALLOWED = {
    "features/ELEVATION_PROFILE.md": "its own sections are 'Decision 1', 'Decision 2'",
    "client/src/lib/ribbonView.ts": "cites features/ELEVATION_PROFILE.md's 'Decision 1'",
    "features/AUTHENTICATION.md": "cites ACCOUNT_SYNC.md's open decision 5",
    "features/mockups/hiker-mark.html": "a mock-up's own numbered list",
    "pipeline/sources.json": "cites #1533's decision 2",
    "pipeline/spike_central_park_paths.py": "cites #1533's decision 2",
    "pipeline/spike_package_overlap.py": "names issue #193, 'the decision #193 exists to make'",
    ".github/tests/test_no_decision_numbers.py": "this file's own examples of what the pattern finds",
}

#: The pipeline's Python, its repo tests, workflows and scripts, which already hold to the rule. The rest of
#: the repository follows once the docs, dbt and extract cleanups land (test_no_file_cites_a_decision_by_number).
CLEANED = (
    ".github/",
    "scripts/",
    "pipeline/lib/",
    "pipeline/tests/",
)
NOT_YET_CLEANED = (
    "pipeline/make_dbt_",
    "pipeline/generate_",
    "pipeline/tests/test_extract",
    "pipeline/tests/test_sources",
    "pipeline/tests/test_not_available",
    "pipeline/tests/test_dbt_",
    "pipeline/tests/test_generated_",
    "pipeline/tests/test_source_freshness.py",
)

#: Larger than any hand-written file here; a lock file or a generated bundle is not prose.
MAX_BYTES = 2_000_000


def _tracked() -> list[str]:
    listed = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return listed.stdout.splitlines()


def _citations(paths: list[str]) -> dict[str, list[str]]:
    """{path: ['line N: decision 204', ...]} for every tracked text file in `paths` not in ALLOWED."""
    found: dict[str, list[str]] = {}
    for path in paths:
        if path in ALLOWED or path.endswith(("package-lock.json", ".lock")):
            continue
        file = REPO_ROOT / path
        if not file.is_file() or file.stat().st_size > MAX_BYTES:
            continue
        data = file.read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="ignore")
        hits = [f"line {text.count(chr(10), 0, m.start()) + 1}: {m.group(0)!r}" for m in DECISION_NUMBER.finditer(text)]
        if hits:
            found[path] = hits
    return found


def _in_cleaned_area(path: str) -> bool:
    top_level_python = path.startswith("pipeline/") and path.count("/") == 1 and path.endswith(".py")
    return (top_level_python or path.startswith(CLEANED)) and not path.startswith(NOT_YET_CLEANED)


def test_the_pattern_finds_a_decision_number_and_passes_a_date():
    assert DECISION_NUMBER.search("as decision 204 says")
    assert DECISION_NUMBER.search("(DECISION 61'S HOUR)")
    assert DECISION_NUMBER.search("elevation_profile_max_null_share (decision\n#: 194: above it")
    assert DECISION_NUMBER.search("decision 28a")
    assert not DECISION_NUMBER.search("the maintainer's decision 2026-09-09 removed them")
    assert not DECISION_NUMBER.search("a decision about blast radius")


def test_the_pipelines_python_repo_tests_workflows_and_scripts_cite_no_decision_by_number():
    found = _citations([path for path in _tracked() if _in_cleaned_area(path)])
    assert not found, f"state the choice instead of its decision number: {found}"


@pytest.mark.xfail(
    reason="the docs, dbt and extract cleanups of PR #1805 have not merged yet; un-mark once they have",
    strict=False,
)
def test_no_file_cites_a_decision_by_number():
    found = _citations(_tracked())
    assert not found, f"state the choice instead of its decision number: {sorted(found)}"


def test_every_allowed_file_still_exists_and_still_needs_its_exception():
    tracked = set(_tracked())
    for path in ALLOWED:
        assert path in tracked, f"{path} is gone: take it out of ALLOWED"
        text = (REPO_ROOT / path).read_text(encoding="utf-8", errors="ignore")
        assert DECISION_NUMBER.search(text), f"{path} cites no decision by number any more: take it out of ALLOWED"
