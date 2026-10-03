"""publish-conditions.yml's dlt extract runs with its own leg's conditions database URL and no other.

The extract step's env names both legs' secrets literally (PRODUCTION_URL and
UA_URL; "Is there a database to read" says why), and the script exports one
of them as CONDITIONS_DATABASE_URL. dlt and the rest of
requirements-extract.txt then run in that process, so both names are unset
first: a UA soak run never carries production's URL.

The step's own script runs here under bash, with a stand-in for the extract's
python that writes down the environment it was started with.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-conditions.yml"
STEP = "Extract this leg's closures and warnings into the raw store (dbt path)"


def _step() -> dict:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["publish"]["steps"]
    return next(step for step in steps if step.get("name") == STEP)


def _run_extract(tmp_path: Path, environment: str) -> dict[str, str]:
    python = tmp_path / "extract" / "bin" / "python"
    python.parent.mkdir(parents=True)
    seen = tmp_path / "env.txt"
    python.write_text(f'#!/bin/bash\nenv > "{seen}"\n')
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "ENVIRONMENT": environment,
        "LEG": f"conditions_{environment}",
        "PRODUCTION_URL": "postgresql://production.invalid/conditions",
        "UA_URL": "postgresql://ua.invalid/conditions",
        "R2_RAW_BUCKET": "raw-bucket",
    }
    subprocess.run(["bash", "-e", "-c", _step()["run"]], env=env, check=True, capture_output=True, text=True)
    return dict(line.split("=", 1) for line in seen.read_text().splitlines() if "=" in line)


def test_the_step_names_both_legs_secrets_and_picks_one():
    """The case this file guards exists: both URLs are in the step's env."""
    env = _step()["env"]
    assert env["PRODUCTION_URL"] == "${{ secrets.PRODUCTION_CONDITIONS_DATABASE_URL }}"
    assert env["UA_URL"] == "${{ secrets.UA_CONDITIONS_DATABASE_URL }}"


@pytest.mark.parametrize(("environment", "url"), [("ua", "ua.invalid"), ("production", "production.invalid")])
def test_the_extract_runs_with_its_own_legs_url_alone(tmp_path, environment, url):
    seen = _run_extract(tmp_path, environment)

    assert url in seen["CONDITIONS_DATABASE_URL"]
    assert "PRODUCTION_URL" not in seen
    assert "UA_URL" not in seen
    other = "production.invalid" if environment == "ua" else "ua.invalid"
    assert [name for name, value in seen.items() if other in value] == []
