"""publish-conditions.yml's publish job ends inside its own cap: the publish first, then the steps after it.

A step that hits its `timeout-minutes` fails the job, and every step after it
is skipped, "Publish to R2" among them: NWS's alerts, OurHike's own closures
and the drought bands all miss that hour. The build step's cap was 4 minutes
while soak run 538 spent 182 s of its 240 in it.

THE FIGURES ARE MEASURED, from the GitHub API's step times for the UA leg of
the dbt path's 39 soak runs 617 to 676 (2026-10-10 12:21 to 2026-10-15 02:47
UTC, read 2026-10-15): the build step took 195 to 360 s, and the rest of the
job, its time less the build, the freshness step and the hand-off, 140 to
213 s. They replace the seven runs 529 to 539 of 2026-10-04 and 05, 182 s and
179 s, measured before the extract, Elementary and the hand-off were in it.

WHAT IS HELD, in the order a run reaches it:
- the build's cap is half again above its slowest measured build;
- a build at its cap still publishes, with the trail lines' restore stalled to
  its own cap before it;
- the build, the restore and the freshness step all at their caps, with the
  rest at its slowest, still end inside the job's cap, so the freshness step
  ends with its own answer: 600 + 60 + 60 + 213 = 933 s of 960;
- the hand-off between them takes only what the job has left after every
  step that follows it, so it is never the step that runs the job into its
  cap;
- client/src/lib/noticeSelection.ts's SAME_BUILD_MS is the job's cap, as its
  own reasoning says it must be.

THE JOB'S CAP IS 16 MINUTES (the maintainer, 2026-10-15): at 15, the joint
sum above ran 33 s past the cap. The build step's cap is 10 minutes.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-conditions.yml"
HAND_OFF = "Hand this build's warehouse to its checks (dbt path)"
RESTORE = "Restore the release's trail lines for the area closures' cut (dbt path)"
CLOCK = "Note when this job started, for the hand-off's share of its cap"

#: Run 669 (38646751834): 2026-10-14 22:18 UTC, the slowest build of the 39.
SLOWEST_BUILD_SECONDS = 360
#: Run 666 (38612472566): a 636 s job whose build took 357 s, its freshness step 16 s and its hand-off 50 s; the first
#: run after three days without one, whose extract read for 111 s where the others took 62 to 76.
SLOWEST_REST_OF_JOB_SECONDS = 213
#: The steps after the freshness step, and the job's end: 2 to 5 s on the 39 runs.
SLOWEST_AFTER_FRESHNESS_SECONDS = 5
#: "Set up job", which runs before the job's own steps and so before CLOCK reads the time: 0 to 3 s on the 39 runs.
SLOWEST_SET_UP_SECONDS = 3
#: @unvalidated: half as much again as the slowest build is picked, not derived. The builds above already spread
#: from 195 to 360 s, and the median of the last eight (2026-10-14 and 15, two commits) was 337 s against 281 s for
#: the first 31 (2026-10-10 and 11, six commits). A few weeks of the summary's `build_marts.py --lane hourly` line
#: would show how fast the build actually grows.
HEADROOM = 1.5


def _job() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["publish"]


def _named(name: str) -> dict:
    (step,) = [step for step in _job()["steps"] if step.get("name") == name]
    return step


def _build_step() -> dict:
    (step,) = [step for step in _job()["steps"] if step.get("id") == "build"]
    return step


def _freshness_step() -> dict:
    (step,) = [step for step in _job()["steps"] if 'dbt/bin/dbt" source freshness' in str(step.get("run", ""))]
    return step


def test_the_build_steps_cap_is_half_again_above_the_slowest_measured_build():
    cap = _build_step()["timeout-minutes"] * 60
    assert cap >= SLOWEST_BUILD_SECONDS * HEADROOM, f"a {cap} s cap over a build measured at {SLOWEST_BUILD_SECONDS} s"


def test_a_build_that_runs_to_its_cap_still_publishes_beside_a_restore_stalled_to_its_own():
    """Otherwise a build that finished just under its own cap would meet the job's own cap before the publish. The trail
    lines' restore sits before the build, and actions/cache waits 10 minutes on a stalled segment by default, so its cap
    goes on top of the measured rest, which already holds its usual 1.4 s; and it may fail without failing the job."""
    restore = _named(RESTORE)

    assert restore.get("continue-on-error") is True, "a restore that hits its cap is an hour without lines, never a red job"
    caps = (_build_step()["timeout-minutes"] + restore["timeout-minutes"]) * 60
    assert caps + SLOWEST_REST_OF_JOB_SECONDS <= _job()["timeout-minutes"] * 60


def test_the_build_the_restore_and_the_freshness_step_all_at_their_caps_still_end_inside_the_jobs_cap():
    """The freshness step runs after "Publish to R2", so it can never cost a publish, but a check that
    ran into the job's cap would end the run cancelled rather than with its own answer. The hand-off between them yields
    the freshness step its cap (the next test), so the build's cap, the restore's and this one's are added to the rest:
    933 s, which a 900 s job could not hold."""
    job_cap = _job()["timeout-minutes"] * 60
    caps = (_build_step()["timeout-minutes"] + _named(RESTORE)["timeout-minutes"] + _freshness_step()["timeout-minutes"]) * 60
    assert caps + SLOWEST_REST_OF_JOB_SECONDS <= job_cap, f"{caps + SLOWEST_REST_OF_JOB_SECONDS} s against {job_cap}"


def test_the_hand_off_takes_only_what_the_job_has_left_after_every_step_that_follows_it():
    """Each half runs under `timeout` for the smaller of its own ceiling and what the job has left of JOB_SECONDS after
    RESERVE_SECONDS, read off the job's own clock, so the hand-off can never be the step that runs the job into its
    cap, and its own `timeout-minutes` is a backstop above both ceilings that never binds first."""
    steps = _job()["steps"]
    names = [step.get("name") for step in steps]
    hand_off, freshness = _named(HAND_OFF), _freshness_step()
    env = hand_off["env"]
    between = steps[names.index(HAND_OFF) + 1 : names.index(freshness["name"])]
    after = steps[names.index(freshness["name"]) + 1 :]

    assert int(env["JOB_SECONDS"]) == _job()["timeout-minutes"] * 60
    assert (
        int(env["RESERVE_SECONDS"])
        >= freshness["timeout-minutes"] * 60 + SLOWEST_AFTER_FRESHNESS_SECONDS + SLOWEST_SET_UP_SECONDS
    ), "what the freshness step may take, what follows it, and the set-up before the clock was read"
    for step in between:
        # The steps that turn the run red for what the build held back: an echo and an exit, 0 s on all 39 runs.
        assert set(step) <= {"name", "if", "env", "run"} and "python" not in step["run"], step["name"]
    assert all("run" not in step for step in after), "nothing but a cache save after it, which the 2 to 5 s measured"
    ceilings = int(env["BUNDLE_SECONDS"]) + int(env["WAREHOUSE_SECONDS"])
    assert len(re.findall(r"timeout --kill-after=(\d+) ", hand_off["run"])) == 2
    grace = sum(int(each) for each in re.findall(r"timeout --kill-after=(\d+) ", hand_off["run"]))
    assert ceilings + grace < hand_off["timeout-minutes"] * 60, "the backstop never binds before both ceilings"


def test_the_jobs_clock_is_read_before_anything_that_takes_time():
    """After the two refusals, which come first (.github/tests/test_conditions_production_leg_needs_main.py) and take no
    measurable time, and on every leg, since nothing may skip it and leave the hand-off without a clock."""
    names = [step.get("name") or step.get("uses") for step in _job()["steps"]]
    clock = _named(CLOCK)

    assert names.index(CLOCK) == 2 and "if" not in clock
    assert clock["run"] == 'echo "PUBLISH_JOB_STARTED_AT=$(date +%s)" >> "$GITHUB_ENV"'
    assert names.index(CLOCK) < names.index("actions/checkout@v7")
    assert "PUBLISH_JOB_STARTED_AT" in _named(HAND_OFF)["run"]


def test_the_clients_same_build_window_is_the_jobs_cap():
    """client/src/lib/noticeSelection.ts's SAME_BUILD_MS is "publish-conditions.yml's cap on the whole job, which one
    build's snapshots cannot outlast", and moves with it. Read from its text, so
    neither can move without the other."""
    source = (WORKFLOW.parents[2] / "client" / "src" / "lib" / "noticeSelection.ts").read_text(encoding="utf-8")
    (minutes,) = re.findall(r"^export const SAME_BUILD_MS = (\d+) \* 60 \* 1000$", source, re.MULTILINE)

    assert int(minutes) == _job()["timeout-minutes"]
