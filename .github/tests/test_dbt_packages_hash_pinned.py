"""The dbt job and scripts/test.sh check dbt_packages/ against pipeline/dbt/packages.sha256 before dbt reads it.

Decision 144 (pipeline/ELT.md, the maintainer's poll of 2026-10-09): the dbt install and the dbt packages are
hash-pinned. packages.yml and package-lock.yml pin versions only, so pipeline/check_dbt_packages.py compares every
file a package shipped with its committed sha256. It has to run after the packages land (a cache hit or `dbt deps`)
and before `dbt parse`, the first command that reads them.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHECK = "check_dbt_packages.py"


def _dbt_job_steps() -> list[dict]:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "pipeline-tests.yml").read_text(encoding="utf-8"))
    return workflow["jobs"]["dbt"]["steps"]


def _index(steps: list[dict], predicate) -> int:
    found = [n for n, step in enumerate(steps) if predicate(step)]
    assert len(found) == 1, found
    return found[0]


def test_the_dbt_job_checks_its_packages_after_they_land_and_before_dbt_parse():
    steps = _dbt_job_steps()
    check = _index(steps, lambda step: CHECK in str(step.get("run", "")))
    deps = _index(steps, lambda step: step.get("id") == "deps")
    restore = _index(steps, lambda step: step.get("id") == "dbt-packages")
    parse = _index(steps, lambda step: str(step.get("run", "")).startswith("dbt parse"))
    assert restore < deps < check < parse
    assert steps[check].get("working-directory") == "pipeline"
    assert "cache-hit" not in str(steps[check].get("if", "")), "a cache hit is checked as well as a fresh deps"


def test_the_check_script_is_in_the_dbt_jobs_changed_paths():
    assert f"pipeline/{CHECK}" in (ROOT / ".github" / "workflows" / "pipeline-tests.yml").read_text(encoding="utf-8")


def test_scripts_test_sh_checks_the_packages_between_deps_and_parse():
    text = (ROOT / "scripts" / "test.sh").read_text(encoding="utf-8")
    deps, check, parse = text.index('step "dbt deps"'), text.index(CHECK), text.index('step "dbt parse"')
    assert deps < check < parse
