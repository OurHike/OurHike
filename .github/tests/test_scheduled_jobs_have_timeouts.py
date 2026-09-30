"""Every job in a scheduled workflow declares `timeout-minutes`.

GitHub's default is six hours. A scheduled job has nobody watching it, so a
network call that accepts the connection and never answers holds the job for
those six hours, and `cancel-in-progress: false` - which every scheduled
workflow here sets, correctly, so a slow run is never cancelled by the next -
queues the next fire behind it. For the keepalive that is the failure the job
exists to prevent, wearing a green badge.

Measured 2026-09-17: 16 workflows run on a schedule and 3 of them had no
`timeout-minutes` anywhere - supabase-keepalive.yml (11-18 s per run over its
last five), settings-configured.yml and protections-check.yml (17-30 s over
its last four). The caps those got are in their files with the numbers that
sized them; this test is what keeps the next scheduled job from arriving
without one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"


def _scheduled_jobs() -> list[tuple[str, str, dict]]:
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # YAML 1.1 reads a bare `on:` key as the boolean True.
        triggers = workflow.get("on", workflow.get(True, {})) or {}
        if not isinstance(triggers, dict) or "schedule" not in triggers:
            continue
        for job_id, job in (workflow.get("jobs") or {}).items():
            found.append((path.name, job_id, job))
    return found


def test_the_rule_has_something_to_check():
    """Sixteen scheduled workflows on the day this was written; a parse that
    found none would pass the test below over an empty list."""
    assert len({name for name, _, _ in _scheduled_jobs()}) >= 10


@pytest.mark.parametrize(
    ("workflow", "job_id", "job"), _scheduled_jobs(), ids=lambda value: value if isinstance(value, str) else ""
)
def test_every_scheduled_job_declares_a_timeout(workflow, job_id, job):
    timeout = job.get("timeout-minutes")
    assert isinstance(timeout, int) and timeout > 0, (
        f"{workflow}:{job_id} runs on a schedule with no timeout-minutes - GitHub's default is six hours, "
        "and a scheduled job that hangs blocks its own next fire"
    )
