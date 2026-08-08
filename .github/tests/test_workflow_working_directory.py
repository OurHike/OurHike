"""No step runs in a directory that does not exist yet.

A job with `defaults: run: working-directory: backend` applies that to every
`run:` step, including the ones deliberately placed *before*
`actions/checkout` - the cheap gates that decide whether the rest of the job
should happen at all. Nothing has been checked out at that point, so the path
is absent.

What makes it worth a test rather than a fix and a shrug is how it fails.
The step does not fail: bash never starts, and the runner reports

    An error occurred trying to start process '/usr/bin/bash' with working
    directory '/home/runner/work/OurHike/OurHike/backend'. No such file or
    directory

which reads as the runner being broken rather than the workflow being wrong.
migrate.yml's first real run - the merge commit of #407 - died exactly there,
seven seconds in, before it could tell anyone whether the credential it was
built to use was even valid.

This is also a gap in what the rest of this directory checks. The other
suites here read workflows for what they *reference* - settings, artifacts,
publish targets. None of them reads the order steps run in, so a workflow
could be structurally impossible and still pass everything.

The rule: a `run:` step before the job's first `actions/checkout` must not
inherit a relative working-directory, and must not set one either, unless it
is `.` - the workspace root, which the runner creates before any step.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# The workspace root itself always exists - the runner creates it in "Prepare
# workflow directory", before the first step. Anything else named relatively
# is a path a checkout was supposed to bring.
ALWAYS_PRESENT = {".", "./", "${{ github.workspace }}"}


def _workflows():
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml"))


def _is_checkout(step):
    return isinstance(step.get("uses"), str) and step["uses"].startswith("actions/checkout")


def _working_directory(step, job):
    """What this step's `run:` actually resolves in, step overriding job."""
    if "working-directory" in step:
        return step["working-directory"]
    return (job.get("defaults") or {}).get("run", {}).get("working-directory")


def test_no_run_step_before_checkout_needs_a_directory_the_checkout_creates():
    offenders = []
    for path in _workflows():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (workflow.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                if _is_checkout(step):
                    break  # everything after this has a checkout behind it
                if "run" not in step:
                    continue
                directory = _working_directory(step, job)
                if directory is not None and str(directory) not in ALWAYS_PRESENT:
                    offenders.append(
                        f"{path.name}: job '{job_name}', step "
                        f"'{step.get('name', step['run'].splitlines()[0][:40])}' runs in '{directory}' before any "
                        f"actions/checkout"
                    )
    assert not offenders, (
        "These steps run before their job checks anything out, in a directory that only exists afterwards. The runner "
        "reports this as being unable to start bash, not as a failing step, so it reads as infrastructure rather than "
        "as a workflow bug. Set `working-directory: .` on the step, or move it after the checkout:\n  " + "\n  ".join(offenders)
    )


def test_the_rule_has_something_to_check():
    """A guard against the test above passing because it found no pre-checkout
    steps at all - which is what it would do if `_is_checkout` stopped matching
    (a move to a different action, say) and every job broke on its first step.
    """
    seen = 0
    for path in _workflows():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                if _is_checkout(step):
                    break
                if "run" in step:
                    seen += 1
    assert seen, (
        "No workflow has a `run:` step before its checkout, so the rule above checked nothing. Either the pattern of "
        "gating a job before checking out has been abandoned - in which case delete both tests - or _is_checkout has "
        "stopped recognising the checkout action."
    )
