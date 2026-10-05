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

import re
import subprocess
import sys
from pathlib import Path

import pytest

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
    # Behaviour held in test_night_queue.py (#1463). The fetch half is here
    # for the parse check only - it shells out to curl against the live API,
    # which is what TESTING.md's small-synthetic-fixture rule keeps out of CI.
    REPO_ROOT / "scripts" / "nightshift.sh",
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


def test_the_dbt_suite_reads_the_dbt_jobs_own_scope_not_the_pytest_jobs():
    """pipeline-tests.yml carries two suites, and the scope reading used to
    stop at the first changed-paths step it met - the pytest job's - so the
    dbt job's list was never read and scripts/test.sh ran no dbt at all
    (#1793 — Rebuild the data platform as dlt → dbt: seven contracted marts,
    a monthly refresh, published docs, and lighter phone downloads). The
    dbt job's list names files inside pipeline/ one by one; the pytest
    job's names pipeline/ whole."""
    dbt = _scope("dbt").split()
    pipeline = _scope("pipeline").split()

    assert "pipeline/dbt/" in dbt
    assert "pipeline/.sqlfluff" in dbt
    assert "pipeline/" not in dbt, "this is the pytest job's scope, read for the dbt suite"
    assert "pipeline/" in pipeline


def test_test_sh_runs_every_suite_suite_scopes_knows():
    """A suite added to suite_scopes.py and not to test.sh's suite_names is
    read, matched, and then never run - the quiet half of the drift #660
    was about."""
    test_sh = (REPO_ROOT / "scripts" / "test.sh").read_text(encoding="utf-8")
    names_line = next(line for line in test_sh.splitlines() if line.startswith("suite_names=("))
    named = set(names_line.split("(", 1)[1].rstrip(")").split())

    listed = subprocess.run([sys.executable, str(SUITE_SCOPES)], capture_output=True, text=True, check=True)
    known = {line.split()[0] for line in listed.stdout.splitlines() if line.strip()}

    assert known <= named, f"suites test.sh never runs: {sorted(known - named)}"


def test_the_client_scope_carries_the_entries_whose_absence_was_the_drift():
    """threads.sh's hand copy was missing exactly these (#660), so the
    ledger reported `none (docs only)` for changes CI runs the client suite
    on - the blind spot behind CLAUDE.md's second issue collision."""
    scope = _scope("client")
    assert "site/" in scope
    assert "pipeline/reference/" in scope
    assert ".github/ISSUE_TEMPLATE/" in scope


@pytest.mark.parametrize(
    "path",
    [
        # client/src/lib/dataRelease.pointer.test.ts and config.phoneFileKey.test.ts
        "channels.json",
        # client/src/lib/config.phoneFileKey.test.ts, which reads every *.yml there
        "pipeline/dbt/models/publish/_publish__elevation.yml",
    ],
)
def test_the_client_scope_covers_the_files_decision_44s_client_tests_read(path):
    """client-tests.yml's own rule: a suite's scope includes every file its
    tests read. Without these, the promotion pull request, which changes
    channels.json and nothing else, ran no check of its entries against the
    client's release-id rule. Matched as changed-paths matches, by prefix."""
    assert any(path.startswith(prefix) for prefix in _scope("client").split()), path


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


def _test_sh_parity_families(test_sh: str) -> set[str]:
    """The parity families test.sh's dbt suite runs: its `for family in ...` lists and its direct parity.py lines."""
    runs = {item.split(":")[0] for loop in re.findall(r"for family in ([a-z0-9_: ]+); do", test_sh) for item in loop.split()}
    return runs | set(re.findall(r"parity\.py ([a-z0-9_]+) --new", test_sh))


def test_test_sh_list_names_every_ci_dbt_parity_family_and_step_its_dbt_suite_leaves_out():
    """WF8 of the PR #1805 review: test.sh's dbt suite ran 6 of the 47 parity families pipeline-tests.yml's dbt job
    runs, and not its contract-versions step, while its comment said it followed that job "step for step". A change
    that broke one of the other 41 passed test.sh and failed CI. `--list` now names every one it leaves out, from
    CI's own step (scripts/dbt_ci_parity.py), and the array test.sh compares with is the families it runs."""
    from test_refresh_reference import _ci_families

    test_sh = (REPO_ROOT / "scripts" / "test.sh").read_text(encoding="utf-8")
    runs = _test_sh_parity_families(test_sh)
    (declared,) = re.findall(r"^dbt_local_parity=\(([a-z0-9_ ]+)\)$", test_sh, re.M)
    assert set(declared.split()) == runs, "dbt_local_parity is not the families test.sh's parity lines run"

    script = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "dbt_ci_parity.py")], capture_output=True, text=True, check=True
    )
    assert script.stdout.split() == list(_ci_families()), "scripts/dbt_ci_parity.py does not read CI's step"

    listed = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "test.sh"), "--all", "--list"], capture_output=True, text=True, check=True
    )
    (line,) = [line for line in listed.stdout.splitlines() if "parity families" in line]
    named = set(line.split(" not run here: ", 1)[1].split(";", 1)[0].split())
    assert named == set(_ci_families()) - runs and named, line
    assert "check_contract_versions.py" in line, line


def test_an_unknown_suite_is_an_error_not_an_empty_answer():
    result = subprocess.run(
        [sys.executable, str(SUITE_SCOPES), "typo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "unknown suite" in result.stderr


def test_only_test_sh_may_leave_webkit_out_and_ci_never_does():
    """#1537. FLOW_SKIP_WEBKIT drops the flow suite's phone-webkit project, so
    an agent sandbox with Chromium alone can pass scripts/test.sh. It must stay
    a local, announced skip: set by test.sh only beside the line saying so,
    and by no workflow, so a CI runner that lost WebKit still goes red."""
    test_sh = (REPO_ROOT / "scripts" / "test.sh").read_text(encoding="utf-8")
    config = (REPO_ROOT / "client" / "playwright.config.ts").read_text(encoding="utf-8")

    assert "process.env.FLOW_SKIP_WEBKIT === '1'" in config
    setter = test_sh.index("flow_env=(FLOW_SKIP_WEBKIT=1)")
    assert "phone-webkit SKIPPED" in test_sh[test_sh.rindex("if !", 0, setter) : setter]
    assert "SKIPPED: " in test_sh[test_sh.index("== all green") - 400 :]

    for workflow in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        assert "FLOW_SKIP_WEBKIT" not in workflow.read_text(encoding="utf-8"), workflow.name
