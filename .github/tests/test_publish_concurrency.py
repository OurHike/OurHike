"""Every workflow that runs publish.py joins one concurrency group.

`pipeline/publish.py` reads the environment's `latest.json`, uploads for as
long as the artifacts take, and writes the merged manifest last. Nothing in
that sequence notices the bucket changing underneath it, so mutual exclusion
between writers is the whole defence: two concurrent publishes interleave,
and whichever writes last reverts the other's manifest entries while the
objects keep the newer bytes - the pointer every client fetches first, left
describing artifacts that are no longer there.

Checked rather than remembered, because the last workflow to join the roster
did not join the group (#645 - publish-conditions.yml): its header argued its
own matrix legs write disjoint keys, which was true and answered a different
question. The race is never between one workflow's jobs; it is between
workflows, over the shared manifest. A new workflow that invokes publish.py
either joins `publish-data` or fails here by name.

One kind of job is named here instead: one that runs publish.py only as
`python publish.py --sidecar <key>` (publish_sidecar()), which reads and
writes no latest.json and so is outside the race above. SIDECAR_ONLY names
each with its reason, and holds it to `--sidecar` alone.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

PUBLISH_GROUP = "publish-data"


#: Jobs whose every publish.py line is `python publish.py --sidecar <key>`: publish_sidecar() puts that one dbt
#: sidecar in place and touches no latest.json, no artifact and no release folder, so the race this file guards cannot
#: involve it, and each holds a group of its own instead, named here with why.
SIDECAR_ONLY = {
    # Decision 110: the hourly lane's checks put conditions/data_quality.json in place after the build has published,
    # holding conditions-checks-<leg>, a group no publisher holds. In publish-data, or in any group a publisher holds,
    # every checks run would be an entrant that cancels a publisher queued there (#1513 - A queued publish is silently
    # cancelled when another one joins publish-data, and it looks like a green build).
    ("check-conditions.yml", "check"),
}


def _publish_lines(job: dict) -> list[str]:
    """Each line of the job's steps that runs publish.py: the command at the start of its own line, alone or with
    its arguments."""
    lines = (line.strip() for step in job.get("steps") or [] for line in str(step.get("run", "")).splitlines())
    return [line for line in lines if line == "python publish.py" or line.startswith("python publish.py ")]


def publishing_jobs() -> list[tuple[str, str, dict, dict]]:
    """(file, job id, workflow, job) for every job with a step that actually
    invokes publish.py, SIDECAR_ONLY's jobs among them.

    A whole-string search for "publish.py" over-matches: publish-vector-data.yml's
    `build` job (#1265) has a diagnostic step that imports `from publish import
    collect_photos` and comments on what "publish.py already orders" - neither
    writes anything, and a substring match flagged the job anyway once #1265 gave
    it a concurrency group of its own to disagree with the real publisher's. Every
    actual invocation in this repository is the literal command at the start of
    its own line, so that is what is matched instead."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_id, job in (workflow.get("jobs") or {}).items():
            if _publish_lines(job):
                found.append((path.name, job_id, workflow, job))
    return found


def test_the_rule_has_something_to_check():
    """Five writers today. A rename or a refactor that moved the publish step
    out of `run:` would otherwise turn the assertion below into a pass over
    an empty list - the vacuous green test_repository_settings.py guards its
    own idiom against."""
    assert len(publishing_jobs()) >= 5


def _groups(workflow: dict, job: dict) -> set[str]:
    """The concurrency groups a job holds, its own and its workflow's, each written as a mapping or a bare string."""
    found = set()
    for holder in (job, workflow):
        concurrency = holder.get("concurrency")
        group = concurrency if isinstance(concurrency, str) or concurrency is None else concurrency.get("group")
        if group:
            found.add(group)
    return found


def test_every_publisher_shares_the_group():
    """At the job's level or its workflow's. A job may hold a group of its own beside its workflow's: the workflow's
    group holds the whole run whatever its jobs' own groups are, so either level holding publish-data is the job
    holding it."""
    for name, job_id, workflow, job in publishing_jobs():
        if (name, job_id) in SIDECAR_ONLY:
            continue
        groups = _groups(workflow, job)
        assert PUBLISH_GROUP in groups, (
            f"{name}:{job_id} runs publish.py outside concurrency group "
            f"{PUBLISH_GROUP!r} - see #645 for what two concurrent writers "
            "do to latest.json"
        )


def test_a_sidecar_only_job_runs_publish_py_with_sidecar_alone_and_holds_no_publish_data():
    """Each SIDECAR_ONLY job exists and runs publish.py only to put a sidecar in place, so one that grew a full publish
    would fall back under the rule above by failing here. And it holds no publish-data at either level, the reason it
    is named at all."""
    jobs = {(name, job_id): (workflow, job) for name, job_id, workflow, job in publishing_jobs()}
    for key in sorted(SIDECAR_ONLY):
        assert key in jobs, f"{key} runs no publish.py, so SIDECAR_ONLY names a job that is gone"
        workflow, job = jobs[key]
        lines = _publish_lines(job)
        assert lines and all(line.startswith("python publish.py --sidecar ") for line in lines), (key, lines)
        assert PUBLISH_GROUP not in _groups(workflow, job), f"{key} holds {PUBLISH_GROUP}: take it out of SIDECAR_ONLY"


def test_no_publisher_shares_any_concurrency_group_with_a_sidecar_only_job():
    """#1513's cancellation is not publish-data's alone: GitHub keeps one pending run per group, so a SIDECAR_ONLY job
    in any group a publisher also holds can take the slot that publisher waits in and cancel it, with nothing red.
    check-conditions.yml's legs shared conditions-history-<leg> with publish-conditions.yml's until the review of
    PR #1805 found exactly that (finding 3)."""
    jobs = {(name, job_id): (workflow, job) for name, job_id, workflow, job in publishing_jobs()}
    sidecars = {key: _groups(*jobs[key]) for key in sorted(SIDECAR_ONLY) if key in jobs}
    assert sidecars, "SIDECAR_ONLY names no job that runs publish.py, so this checked nothing"
    for (name, job_id), (workflow, job) in sorted(jobs.items()):
        if (name, job_id) in SIDECAR_ONLY:
            continue
        for key, groups in sidecars.items():
            shared = sorted(_groups(workflow, job) & groups)
            assert not shared, f"{name}:{job_id} shares {shared} with {key}, which can cancel its queued run"
