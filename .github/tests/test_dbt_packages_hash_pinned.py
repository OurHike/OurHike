"""Every job that runs `dbt deps`, and the docs site's build.sh, check dbt_packages/ against pipeline/dbt/packages.sha256
before dbt reads it, and only a tree that passed is ever saved to the cache.

Decision 144 (pipeline/ELT.md, the maintainer's poll of 2026-10-09): the dbt install and the dbt packages are
hash-pinned. packages.yml and package-lock.yml pin versions only, so pipeline/check_dbt_packages.py compares every
file a package shipped with its committed sha256. It has to run after the packages land (a cache hit or `dbt deps`),
before the first command that reads them, and before the save: a tree saved without passing would be what every
later hit restores, until the key changed.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from test_dbt_packages_cache import JOBS_THAT_RUN_DEPS, PACKAGES, WORKFLOWS

ROOT = Path(__file__).resolve().parents[2]
CHECK = "check_dbt_packages.py"

#: A dbt command, as these workflows write one (`dbt parse`, `"$RUNNER_TEMP/dbt/bin/dbt" build`), or the script that
#: runs dbt build. Prose in an echo ("The dbt path") does not match.
READS_PACKAGES = re.compile(
    r"(?:^|[\s/\"'(])dbt\"?\s+(?:build|run|parse|test|compile|docs|source|seed|snapshot|ls|list|show|retry|run-operation)\b"
    r"|build_marts\.py"
)


def _steps(workflow: str, job: str) -> list[dict]:
    return yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))["jobs"][job]["steps"]


def _one(steps: list[dict], predicate, where: str, what: str) -> int:
    found = [n for n, step in enumerate(steps) if predicate(step)]
    assert len(found) == 1, f"{where}: {len(found)} steps {what}, not one"
    return found[0]


def test_every_job_that_runs_deps_checks_its_packages_after_they_land_before_dbt_reads_them_and_before_the_save():
    for workflow, job in sorted(JOBS_THAT_RUN_DEPS):
        where = f"{workflow}:{job}"
        steps = _steps(workflow, job)
        restore = _one(
            steps,
            lambda step: (
                str(step.get("uses", "")).startswith("actions/cache/restore")
                and PACKAGES in str((step.get("with") or {}).get("path", ""))
            ),
            where,
            "restore the packages",
        )
        save = _one(
            steps,
            lambda step: (
                str(step.get("uses", "")).startswith("actions/cache/save")
                and PACKAGES in str((step.get("with") or {}).get("path", ""))
            ),
            where,
            "save the packages",
        )
        deps = _one(steps, lambda step: step.get("id") == "deps", where, "have id deps")
        check = _one(steps, lambda step: CHECK in str(step.get("run", "")), where, f"run {CHECK}")

        assert restore < deps < check < save, where
        assert "cache-hit" not in str(steps[check].get("if", "")), f"{where}: a cache hit is checked as well as a deps"
        check_id = steps[check].get("id")
        assert check_id and f"steps.{check_id}.outcome == 'success'" in str(steps[save].get("if", "")), (
            f"{where}: the save does not wait for the check (its if: {steps[save].get('if')!r})"
        )
        early = [steps[n].get("name") for n in range(check) if READS_PACKAGES.search(str(steps[n].get("run", "")))]
        assert early == [], f"{where}: {early} read the packages before they are checked"
        # The job's default directory, or the step's own, is pipeline/, where the script sits.
        assert steps[check].get("working-directory", "pipeline") == "pipeline", where


def test_the_check_script_is_in_the_dbt_jobs_changed_paths():
    assert f"pipeline/{CHECK}" in (WORKFLOWS / "pipeline-tests.yml").read_text(encoding="utf-8")


def test_the_docs_site_build_checks_the_packages_whether_or_not_it_ran_deps_and_before_dbt_docs_generate():
    text = (ROOT / ".github" / "actions" / "dbt-docs-site" / "build.sh").read_text(encoding="utf-8")
    deps = text.index("dbt deps --profiles-dir .")
    branch_ends = text.index("\nfi\n", deps)
    check = text.index(f"../{CHECK}")
    generate = text.index("dbt docs generate")
    assert deps < branch_ends < check < generate


def test_scripts_test_sh_checks_the_packages_between_deps_and_parse():
    text = (ROOT / "scripts" / "test.sh").read_text(encoding="utf-8")
    deps, check, parse = text.index('step "dbt deps"'), text.index(CHECK), text.index('step "dbt parse"')
    assert deps < check < parse
