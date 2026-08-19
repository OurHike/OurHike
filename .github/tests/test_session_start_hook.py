"""The session-start hook has to provision the suites, or say it did not.

WHY THIS SUITE AND NOT THE PIPELINE ONE. The hook is repository configuration
in the same sense the workflows are: it decides whether a web session can run
anything at all, and it is not owned by any of the three Python trees it
installs. It lives here beside `test_dev_scripts.py` for that reason.

WHAT WENT WRONG TWICE, which is what these tests pin (#822):

  1. `pip_install_pinned` passed a constraints file containing extras, pip
     refused the whole install, and **every web session for weeks provisioned
     no Python dependencies for any of the three suites**. The hook's own
     comment records it.
  2. The hook called bare `pip`, which on the web image is Debian's 3.11,
     while `pipeline/requirements.txt` pins `numpy==2.5.2` - numpy 2.5
     requires >= 3.12. `set -euo pipefail` ended the run at the first pinned
     install, before the dev requirements that carry pytest.

Both failures were **silent and total**, and both surfaced hours later as
"No module named pytest" during unrelated work, reading like a broken
container rather than a broken hook. Neither would have survived a check that
the hook achieved anything, which is why the hook now ends with one and why
these tests exist.

These are static checks on the script's text. They cannot prove an install
works - only a real run does that - but they catch the two shapes that have
actually bitten, and they are the half that can run in CI.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "session-start.sh"
WORKFLOWS = ROOT / ".github" / "workflows"


@pytest.fixture(scope="module")
def hook_text() -> str:
    return HOOK.read_text(encoding="utf-8")


def test_the_hook_is_valid_bash():
    """`bash -n` parses without executing. A syntax error here would fail every
    session at startup, and the script is edited far more often than it is run
    end to end by whoever is editing it."""
    result = subprocess.run(["bash", "-n", str(HOOK)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_python_is_chosen_rather_than_inherited(hook_text):
    """The #822 regression, pinned. `pip install` and `python -` take whatever
    `python3` happens to be, which on the web image is the OLDEST interpreter
    installed and the one the pins reject."""
    offenders = [
        line.strip()
        for line in hook_text.splitlines()
        if re.match(r"^\s*(pip|python)\s+", line) and not line.strip().startswith("#")
    ]

    assert offenders == [], f"the hook must install with the interpreter it selected, not a bare `pip`/`python`: {offenders}"


def test_the_interpreter_is_selected_before_anything_installs(hook_text):
    """Ordering, not just presence: a picker defined after the first install
    would leave `${PY}` empty for it, and `set -u` would abort on a run that
    looked correct in review."""
    picked = hook_text.index('PY="$(pick_python)"')
    first_install = hook_text.index("-m pip install")

    assert picked < first_install


def test_ci_s_python_version_is_read_from_the_workflow_not_copied(hook_text):
    """One home for the version. A number copied into the hook is a number that
    disagrees with CI the first time CI moves, silently and in the direction of
    installing against the wrong interpreter."""
    assert "python-version" in hook_text, "the hook should parse CI's version out of a workflow"
    assert not re.search(r'CI_PYTHON="?3\.\d+', hook_text), "CI's version must not be hardcoded"


def test_the_workflow_the_hook_reads_actually_declares_a_version():
    """The parse has a real target. If the workflow stopped declaring
    `python-version`, `pick_python` would silently fall through to "newest
    installed" - a defensible fallback, but not one anybody chose here."""
    workflow = yaml.safe_load((WORKFLOWS / "pipeline-tests.yml").read_text(encoding="utf-8"))
    declared = {
        step.get("with", {}).get("python-version")
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if isinstance(step, dict) and "setup-python" in str(step.get("uses", ""))
    }

    assert declared - {None}, "pipeline-tests.yml declares no python-version for the hook to read"


def test_the_hook_ends_by_checking_what_it_installed(hook_text):
    """The half both outages were missing. `set -e` proves each command exited
    0; the extras bug exited 0 while installing nothing, so exiting 0 is not
    the same claim as "the suites can run"."""
    assert "gate_check" in hook_text, "the hook must verify its own work"

    checked = set(re.findall(r'gate_check\s+"[^"]*"\s+(\w+)', hook_text))

    # One per Python suite plus the runner itself - the distinction both
    # outages blurred was "this suite can run" against "this suite has nothing".
    assert {"pytest", "duckdb", "fastapi", "yaml"} <= checked, checked


def test_a_failed_check_stops_the_session_rather_than_warning(hook_text):
    """A warning scrolls past and the session proceeds to fail later, somewhere
    unrelated. That is precisely how both outages were experienced."""
    gate = hook_text[hook_text.index("gate_failed=0") :]

    assert re.search(r'if \[ "\$\{gate_failed\}" -ne 0 \]', gate)
    assert "exit 1" in gate


def test_postgres_staying_down_is_a_warning_and_not_fatal(hook_text):
    """The one thing that must NOT be fatal, kept honest in the other
    direction: only the backend suite needs a database, and a hook that aborted
    there would take the other two down with it."""
    assert "WARNING: no local postgres" in hook_text
