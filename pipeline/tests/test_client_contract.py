"""lib/client_contract.py imports nothing outside the standard library.

The deploy guards run check 22 through .github/scripts/check_launch_budget.py
on a runner's bare python3, with nothing installed (ua.yml, pages.yml,
pr-preview.yml). A third-party import here would turn every one of those
deploys red on an ImportError rather than on a release over the budget, so
the property is held here, where a change to the module runs its suite.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import verify_release
from lib import client_contract

PIPELINE = Path(__file__).resolve().parents[1]


def test_the_module_imports_with_no_site_packages():
    """`-S`: no site-packages at all, so only the standard library can be found."""
    done = subprocess.run(
        [sys.executable, "-S", "-c", f"import sys; sys.path.insert(0, {str(PIPELINE)!r}); import lib.client_contract"],
        capture_output=True,
        text=True,
    )

    assert done.returncode == 0, done.stderr


def test_verify_release_reads_check_22_and_the_key_contract_from_their_one_home():
    """The battery runs the same functions publish.py and the guards run, not a copy."""
    assert verify_release.check_launch_budget is client_contract.check_launch_budget
    assert verify_release.expected_client_keys is client_contract.expected_client_keys
    assert verify_release.launch_artifact_budget is client_contract.launch_artifact_budget
    assert verify_release.CLIENT_LIB == client_contract.CLIENT_LIB
