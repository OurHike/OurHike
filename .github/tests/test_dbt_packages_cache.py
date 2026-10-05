"""Every job that runs `dbt deps` takes dbt's packages from the actions cache first, and asks dbt Hub only on a miss.

`dbt deps` reads packages.yml's three packages from hub.getdbt.com and their
tarballs from codeload.github.com. Uncached, every hourly conditions run
depended on both hosts being up at that minute: soak run 538 (2026-10-05,
job 111578158835) logged "Installing dbt-labs/codegen ... Installed 3
packages" at 01:19:19, in a step that runs under `bash -e`, so a failed
download skipped the build and the publish. That is ARCH-6 of the PR #1805
review, and pipeline-tests.yml's dbt job already caches dbt's ADBC driver and
v2's spatial build for the same reason ("so a warm cache rides out an outage
of either host").

What a hit has to be safe for, measured 2026-10-05 on dbt 2.0.6 in a sandbox:
`dbt parse` with pipeline/dbt/dbt_packages/ in place and no `dbt deps` in that
session finished "'parse' successfully", so restoring the folder is the whole
of what deps hands the steps after it.

The key hashes packages.yml and package-lock.yml, which between them pin every
package's version, so a key cannot name two different package sets. The save
runs only after a deps that succeeded: a deps that failed halfway can leave a
partial dbt_packages/, and caching that under the lock's key would make every
later hit skip deps and build on it.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
PACKAGES = "pipeline/dbt/dbt_packages"
KEY_FILES = "hashFiles('pipeline/dbt/packages.yml', 'pipeline/dbt/package-lock.yml')"
DEPS = re.compile(r"\bdbt\"?\s+deps\b")

#: (workflow, job id): every job in .github/workflows that runs `dbt deps` today.
JOBS_THAT_RUN_DEPS = {
    ("pipeline-tests.yml", "dbt"),
    ("publish-conditions.yml", "publish"),
    ("refresh-reference.yml", "build"),
}


def _jobs():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_id, job in (workflow.get("jobs") or {}).items():
            yield path.name, job_id, job.get("steps") or []


def _deps_steps(steps: list[dict]) -> list[int]:
    return [index for index, step in enumerate(steps) if DEPS.search(str(step.get("run", "")))]


def test_the_jobs_listed_here_are_every_job_that_runs_dbt_deps():
    """A new job running `dbt deps` must join the list, so the test below checks its cache too."""
    found = {(name, job_id) for name, job_id, steps in _jobs() if _deps_steps(steps)}
    assert found == JOBS_THAT_RUN_DEPS


def test_each_job_restores_the_packages_before_deps_runs_deps_only_on_a_miss_and_saves_only_what_deps_wrote():
    problems = []
    for name, job_id, steps in _jobs():
        if (name, job_id) not in JOBS_THAT_RUN_DEPS:
            continue
        where = f"{name}:{job_id}"
        restores = [
            (index, step)
            for index, step in enumerate(steps)
            if str(step.get("uses", "")).startswith("actions/cache/restore")
            and PACKAGES in str((step.get("with") or {}).get("path", ""))
        ]
        saves = [
            (index, step)
            for index, step in enumerate(steps)
            if str(step.get("uses", "")).startswith("actions/cache/save")
            and PACKAGES in str((step.get("with") or {}).get("path", ""))
        ]
        if len(restores) != 1 or len(saves) != 1:
            problems.append(f"{where}: {len(restores)} restore(s) and {len(saves)} save(s) of {PACKAGES}, not one each")
            continue
        (restore_at, restore), (save_at, save) = restores[0], saves[0]
        key = restore["with"]["key"]
        if KEY_FILES not in key:
            problems.append(f"{where}: the restore's key {key!r} does not hash packages.yml and package-lock.yml")
        if save["with"]["key"] != key:
            problems.append(f"{where}: the save's key {save['with']['key']!r} is not the restore's {key!r}")

        # The job's own deps step: the one whose whole command is deps in pipeline/dbt. The contract check's deps
        # for the base commit is held by the test below.
        own = [index for index in _deps_steps(steps) if "$base" not in str(steps[index].get("run", ""))]
        if len(own) != 1:
            problems.append(f"{where}: {len(own)} steps run its own dbt deps, not one")
            continue
        deps = steps[own[0]]
        if not restore_at < own[0] < save_at:
            problems.append(f"{where}: the restore, deps and the save are not in that order")
        if f"steps.{restore.get('id')}.outputs.cache-hit != 'true'" not in str(deps.get("if", "")):
            problems.append(f"{where}: dbt deps runs on a cache hit too (its if: {deps.get('if')!r})")
        if not deps.get("id") or f"steps.{deps['id']}.outcome == 'success'" not in str(save.get("if", "")):
            problems.append(f"{where}: the save does not wait for a deps that succeeded (its if: {save.get('if')!r})")
    assert problems == []


def test_the_contract_check_copies_the_heads_packages_into_the_base_when_both_pin_files_match():
    """The contract-versions step parses the base commit in a worktree of its own, which needs the base's packages.
    When the base's packages.yml and package-lock.yml are the head's byte for byte, deps there would write what the
    head's dbt_packages/ already holds, so the step copies it and asks dbt Hub only when they differ."""
    steps = yaml.safe_load((WORKFLOWS / "pipeline-tests.yml").read_text(encoding="utf-8"))["jobs"]["dbt"]["steps"]
    (step,) = [step for step in steps if step.get("name") == "Contract versions against the base's manifest"]
    script = step["run"]

    copy_or_fetch = re.compile(
        r'if cmp -s dbt/packages\.yml "\$base/pipeline/dbt/packages\.yml" '
        r'&& cmp -s dbt/package-lock\.yml "\$base/pipeline/dbt/package-lock\.yml"; then\s+'
        r'cp -R dbt/dbt_packages "\$base/pipeline/dbt/dbt_packages"\s+'
        r'else\s+\(cd "\$base/pipeline/dbt" && dbt deps --profiles-dir \.\)\s+fi'
    )
    assert copy_or_fetch.search(script), script
