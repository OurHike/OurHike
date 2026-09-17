"""Carrying the recovered archive is a deliberate act, not something a
routine publish does (#1567).

WHAT THIS EXISTS TO CATCH, because it already happened once. #1550 added the
step that brings the Internet Archive recovery to the runner and gated it on
`include_photos`, an input that defaults to TRUE. The store it builds
(`pipeline/data/raw/wayback_photos`) is not in `FETCH_OUTPUTS`, so it is never
restored from the build cache, so the step's own "already here" exit cannot
fire on a fresh runner. Every vector publish spent ~20 GitHub API calls and
40,609,870 bytes rebuilding a corpus that is finished and cannot change - 403
frozen captures, nothing upstream left to ask for.

Nothing failed. That is the point: the cost was invisible in a green run, and
it was the maintainer noticing the shape of the design rather than any check
that found it.

THE INVARIANT IS ABOUT THE DEFAULT, not about the step existing. The step has
to exist - the park has to be filled once, and a later confirmation batch
needs it again until the server-side copy out of the park is built. What must
not drift back is the step running for anybody who did not ask for it.

`test_photo_stores_reach_the_publish_job.py` is the sibling claim: that the
stores publish.py reads survive the handoff between jobs.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-vector-data.yml"

#: The input that must exist, must default to off, and must be what the step
#: is gated on. Spelled once here.
OPT_IN = "carry_archive_photos"

#: Matched on its prefix rather than in full, so renaming the step's tail does
#: not fail this test - the gate is what is being asserted, not the wording.
STEP_PREFIX = "Carry the confirmed archive"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _dispatch_inputs(document: dict) -> dict:
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    triggers = document.get("on", document.get(True, {}))
    return (triggers.get("workflow_dispatch") or {}).get("inputs", {})


def _carry_step(document: dict) -> dict:
    for job in (document.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if str(step.get("name") or "").startswith(STEP_PREFIX):
                return step
    raise AssertionError(f"{WORKFLOW.name} has no step named {STEP_PREFIX!r} - if it was removed, delete this test too")


def test_the_archive_carry_has_an_input_of_its_own_that_defaults_to_off():
    inputs = _dispatch_inputs(_workflow())
    assert OPT_IN in inputs, (
        f"{OPT_IN} is gone from {WORKFLOW.name}. The carry must be opt-in; see this file's docstring for what "
        "gating it on include_photos cost."
    )
    assert inputs[OPT_IN].get("default") is False, (
        f"{OPT_IN} defaults to {inputs[OPT_IN].get('default')!r}. It must default to false: the corpus is finished, "
        "so carrying it on an unasked-for publish is pure cost."
    )


def test_the_carry_step_is_gated_on_that_input_and_nothing_else():
    gate = str(_carry_step(_workflow()).get("if") or "")
    assert OPT_IN in gate, (
        f"the carry step's `if:` is {gate!r}, which does not mention {OPT_IN}. Gating it on anything that defaults "
        "to true puts a one-time job back on every publish."
    )
    # `include_photos` defaults to true, so reaching the step through it - even
    # as one arm of an `or` - is the defect this file is named for.
    assert not re.search(r"\binclude_photos\b", gate), (
        f"the carry step's `if:` is {gate!r}. include_photos defaults to true, so any path through it runs the "
        "carry for somebody who did not ask."
    )
