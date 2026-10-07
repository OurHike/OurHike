"""publish-conditions.yml's dbt build step has room above its slowest measured build, inside the job's own cap.

A step that hits its `timeout-minutes` fails the job, and every step after it
is skipped, "Publish to R2" among them: NWS's alerts, OurHike's own closures
and the drought bands all miss that hour. The build step's cap was 4 minutes
while soak run 538 spent 182 s of its 240 in it (WF5 of the PR #1805 review,
and the cap half of ARCH-7).

The figures are measured, from the GitHub API's step times for the UA leg of
the dbt path's seven green soak runs 529, 532, 533, 535, 536, 538 and 539
(2026-10-04 and 2026-10-05): the build step took 83 to 182 s, and the rest of
the job 132 to 179 s.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-conditions.yml"

#: Run 538 (37250913570): 01:20:46 to 01:23:48 on 2026-10-05.
SLOWEST_BUILD_SECONDS = 182
#: Run 536 (37247046796): a 350 s job whose build step took 171 s.
SLOWEST_REST_OF_JOB_SECONDS = 179
#: @unvalidated: half as much again as the slowest build is picked, not derived. The builds above already spread
#: from 83 to 182 s, and decision 77's buffer adds unmeasured work to the slowest writer, pub_conditions_notices. A
#: few weeks of the summary's `build_marts.py --lane hourly` line would show how fast the build actually grows.
HEADROOM = 1.5


def _job() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["publish"]


def _build_step() -> dict:
    (step,) = [step for step in _job()["steps"] if step.get("id") == "build"]
    return step


def test_the_build_steps_cap_is_half_again_above_the_slowest_measured_build():
    cap = _build_step()["timeout-minutes"] * 60
    assert cap >= SLOWEST_BUILD_SECONDS * HEADROOM, f"a {cap} s cap over a build measured at {SLOWEST_BUILD_SECONDS} s"


def test_a_build_that_runs_to_its_cap_still_ends_inside_the_jobs_cap():
    """Otherwise a build that finished just under its own cap would meet the job's 10 minutes before the publish."""
    job_cap = _job()["timeout-minutes"] * 60
    assert _build_step()["timeout-minutes"] * 60 + SLOWEST_REST_OF_JOB_SECONDS <= job_cap


def test_a_build_and_the_freshness_step_each_at_its_cap_still_end_inside_the_jobs_cap():
    """The freshness step (decision 100) runs after "Publish to R2", so it can never cost a publish, but a check that
    ran into the job's cap would end the run cancelled rather than with its own answer. The rest of the job was
    measured before the step existed, so its cap is added on top."""
    (freshness,) = [step for step in _job()["steps"] if 'dbt/bin/dbt" source freshness' in str(step.get("run", ""))]
    job_cap = _job()["timeout-minutes"] * 60
    assert _build_step()["timeout-minutes"] * 60 + freshness["timeout-minutes"] * 60 + SLOWEST_REST_OF_JOB_SECONDS <= job_cap
