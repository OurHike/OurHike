"""Every workflow step that pipes a command to `tee` must be able to fail.

THE BUG THIS EXISTS FOR (#514)

`Verify release`'s first dispatch finished in 16 seconds and reported success.
The battery had crashed on an import and hashed nothing; `upload-artifact` even
warned that the verdict file did not exist, and the run was still green.

    run: python verify_release.py "${ARGS[@]}" | tee verify-release.txt

**A pipeline's exit status is its last command's**, and GitHub's default
`bash -e {0}` does not set `pipefail`. So `tee` exited 0 and the step passed.

That is the failure the release gate exists to prevent, occurring inside the
release gate. It is also invisible to every test written for that workflow -
#508 asserted the absence of `--exit-zero` and of `continue-on-error`, and
neither has anything to say about `| tee`.

WHY THIS IS A RULE ABOUT SHAPE RATHER THAN ABOUT TWO FILES

Five workflows use the idiom. Three of them are REPORTERS: they pass
`--exit-zero` on purpose, signal through a tracking issue, and would be wrong
to fail a scheduled run - GitHub emails on every scheduled failure, so a real
outage would send one a day until it was filtered. Masking changes nothing
there, because there is nothing to mask.

The other two are GATES, dispatched by somebody waiting for the answer, where
the exit code IS the answer. So the rule is not "never pipe to tee"; it is
"a step that pipes to tee either declares it does not care about the exit code
(`--exit-zero`) or arranges to see it (`pipefail`)". Anything else is asserting
an exit status that cannot reach it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / "workflows"

# `shell: bash` runs `bash --noprofile --norc -eo pipefail {0}`. An explicit
# `set -o pipefail` inside the script counts too.
PIPEFAIL_MARKERS = ("shell: bash", "pipefail")


def _steps():
    """(workflow name, step) for every step in every workflow."""
    for path in sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml")):
        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job in (parsed.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                yield path.name, step


def _pipes_to_tee(step: dict) -> bool:
    return "| tee" in (step.get("run") or "")


def _sees_its_exit_code(step: dict, defaults: dict) -> bool:
    if step.get("shell") == "bash":
        return True
    return "pipefail" in (step.get("run") or "")


def _declares_it_does_not_care(step: dict) -> bool:
    """A reporter says so in the command itself, which is the honest signal.

    `--exit-zero` is not incidental: it is how `check_deployment.py` and its
    siblings say "report, do not gate". A step carrying it is asserting nothing
    about the exit code, so `tee` swallowing it costs nothing.
    """
    return "--exit-zero" in (step.get("run") or "")


TEE_STEPS = [
    pytest.param(name, step, id=f"{name}::{step.get('name', 'unnamed')}") for name, step in _steps() if _pipes_to_tee(step)
]


def test_some_workflow_actually_uses_the_idiom():
    """If this file ever finds nothing, it has stopped testing anything -
    a rename of the pattern would leave every assertion below vacuously true."""
    assert TEE_STEPS, "no step pipes to `tee`; this file is asserting nothing"


@pytest.mark.parametrize(("name", "step"), [(p.values[0], p.values[1]) for p in TEE_STEPS], ids=[p.id for p in TEE_STEPS])
def test_a_step_that_pipes_to_tee_can_still_fail(name, step):
    """Either it sees its exit code, or it says it does not want it.

    A step that does neither is claiming to gate on something it will never
    observe - the exact state `Verify release` shipped in.
    """
    if _declares_it_does_not_care(step):
        return

    assert _sees_its_exit_code(step, {}), (
        f"{name} step {step.get('name', 'unnamed')!r} pipes to `tee` without `pipefail` and without "
        "`--exit-zero`. Its exit status will be tee's, which is 0 whatever the command did - so a crash "
        "reports success. Add `shell: bash` (which runs with -o pipefail), or pass --exit-zero if it is "
        "meant to report rather than gate. See #514."
    )


def test_the_release_gate_is_one_of_the_ones_that_can_fail():
    """Named explicitly, because it is the one that was broken and the one
    whose whole purpose is to be able to say no."""
    steps = [step for name, step in _steps() if name == "verify-release.yml" and _pipes_to_tee(step)]

    assert steps, "verify-release.yml no longer pipes the battery to tee - update this test with it"
    for step in steps:
        assert not _declares_it_does_not_care(step), "the release gate must not pass --exit-zero; it is a gate"
        assert _sees_its_exit_code(step, {})
