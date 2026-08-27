"""The two developer scripts are reachable by a suite at last (#660).

scripts/test.sh and scripts/threads.sh sat outside every suite's scope -
nothing linted, syntax-checked, or tested either - which is how test.sh's
hand-written settings scope and threads.sh's hand-kept copy of the CI path
gates both drifted without anything going red. This file is the minimum
that stops a recurrence: both scripts must parse, and the one home their
scope lists now come from (scripts/suite_scopes.py) must keep answering
with the entries whose absence WAS the drift.

Deliberately not an integration test of either script's full behaviour:
they shell out to git against the real repository state, which is exactly
what TESTING.md's small-synthetic-fixture rule keeps out of CI. Parse plus
the scope contract is the part that can be held without that.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    REPO_ROOT / "scripts" / "test.sh",
    REPO_ROOT / "scripts" / "threads.sh",
    REPO_ROOT / "scripts" / "pick_python.sh",
    # Its behaviour is held in test_pages_preview_sweep.py; this list is the
    # blanket "nothing in scripts/ is outside every suite" guard, and leaving
    # a file off it is how the drift #660 was about started.
    REPO_ROOT / "scripts" / "sweep-pages-previews.sh",
    # Behaviour held in test_pipeline_scopes.py (#1123).
    REPO_ROOT / "scripts" / "pipelines.sh",
]
SUITE_SCOPES = REPO_ROOT / "scripts" / "suite_scopes.py"


def _scope(suite: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SUITE_SCOPES), suite],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_both_shell_scripts_parse():
    for script in SCRIPTS:
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_suite_scopes_reads_every_suites_workflow():
    """Each answer must carry the suite's own tree - an empty or missing
    answer means the workflow parse broke, which both callers would paper
    over by running everything (test.sh) or shrugging (threads.sh)."""
    assert "client/" in _scope("client")
    assert "pipeline/" in _scope("pipeline")
    assert "backend/" in _scope("backend")


def test_the_client_scope_carries_the_entries_whose_absence_was_the_drift():
    """threads.sh's hand copy was missing exactly these (#660), so the
    ledger reported `none (docs only)` for changes CI runs the client suite
    on - the blind spot behind CLAUDE.md's second issue collision."""
    scope = _scope("client")
    assert "site/" in scope
    assert "pipeline/reference/" in scope
    assert ".github/ISSUE_TEMPLATE/" in scope


def test_no_script_invokes_a_bare_python_or_python3():
    """The #859 regression, pinned. test.sh shelled out to bare `python` ten
    times while the session-start hook installed everything under the
    interpreter CI uses, so the one command CLAUDE.md names died on its first
    step with "No module named ruff" - a message pointing at a package when
    the problem was the interpreter. Both scripts now select through
    scripts/pick_python.sh; a bare `python`/`python3` command word is the
    drift this catches. The `|| echo python3` scope fallbacks and prose in
    comments or error messages are not command words and do not match."""
    for script in [s for s in SCRIPTS if s.name != "pick_python.sh"]:  # the selector itself is exempt
        offenders = [
            line.strip()
            for line in script.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith("#") and {"python", "python3"} & set(line.split())
        ]
        assert offenders == [], (
            f"{script.name} must run Python through the shared selection, not bare `python`/`python3`: {offenders}"
        )


def test_an_unknown_suite_is_an_error_not_an_empty_answer():
    result = subprocess.run(
        [sys.executable, str(SUITE_SCOPES), "typo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "unknown suite" in result.stderr
