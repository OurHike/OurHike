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
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

PUBLISH_GROUP = "publish-data"


def publishing_jobs() -> list[tuple[str, str, dict, dict]]:
    """(file, job id, workflow, job) for every job with a publish.py step."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_id, job in (workflow.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                if "publish.py" in str(step.get("run", "")):
                    found.append((path.name, job_id, workflow, job))
                    break
    return found


def test_the_rule_has_something_to_check():
    """Five writers today. A rename or a refactor that moved the publish step
    out of `run:` would otherwise turn the assertion below into a pass over
    an empty list - the vacuous green test_repository_settings.py guards its
    own idiom against."""
    assert len(publishing_jobs()) >= 5


def test_every_publisher_shares_the_group():
    for name, job_id, workflow, job in publishing_jobs():
        group = (job.get("concurrency") or {}).get("group") or (workflow.get("concurrency") or {}).get("group")
        assert group == PUBLISH_GROUP, (
            f"{name}:{job_id} runs publish.py outside concurrency group "
            f"{PUBLISH_GROUP!r} - see #645 for what two concurrent writers "
            "do to latest.json"
        )
