"""A dry run must not wait on the production reviewer (#1262).

THE GAP THIS FILE'S SUBJECT CLOSES

`publish-vector-data.yml`'s job used to declare `environment: production`
unconditionally, so a dispatch with `publish: false` - which never invokes
`publish.py` and is structurally incapable of writing anything - parked in
`waiting` behind the production reviewer exactly as a real publish did.
Measured 2026-08-19: run 32294671249 queued with `publish: false`, sat
pending, and was cancelled by the next hourly `publish-conditions.yml` bake
into the shared `publish-data` concurrency group - one second after it
queued. #838 named this finding 2: "The gate is right for a real publish and
pure friction for a build-and-check."

WHAT IS ACTUALLY WORTH TESTING ABOUT THE FIX

Not that the environment is sometimes something other than `production` -
that is one line of YAML and reads as its own documentation. The property
worth holding is the one a future edit could undo without meaning to: the
environment gate and "Publish to R2"'s own `if:` have to be asking the
identical question, or one of two failure directions opens back up -

- the environment stops matching the write condition and a dry run waits
  again (#1262's own regression, arriving a second time), or
- worse, the write condition changes on its own and a run that now writes
  no longer names `production` at all, which is the one failure
  RELEASING.md §12 exists to make impossible.

There is no way to catch the second case by reading YAML alone - that needs
a human noticing, or a live dispatch. What this file CAN hold is that the
two conditions are textually the same predicate, spelled the same way - the
same property `test_identity_ledger_regeneration.py`'s
`test_the_reachability_build_is_not_gated_on_the_fetch_input` holds for a
different pair of steps in this same job, and for the same reason: two
hand-kept copies of one question is the drift this repository keeps finding.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-vector-data.yml"


def _job() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["build-and-publish"]


def _named(steps: list[dict], fragment: str) -> dict:
    """The one step whose name contains `fragment`, or a failure naming what
    was there instead - a renamed step must not slip through as a vacuous pass."""
    matches = [step for step in steps if fragment.lower() in (step.get("name") or "").lower()]
    assert len(matches) == 1, f"expected exactly one step matching {fragment!r}, found {[s.get('name') for s in matches]}"
    return matches[0]


def test_the_environment_is_conditional():
    """The regression #1262 fixes: an unconditional `environment: production`
    gates a run that cannot write, which is friction rather than safety."""
    environment = _job().get("environment")
    assert environment != "production", (
        "environment: production is unconditional again - a run with publish: false will wait on "
        "the reviewer for nothing it could ever upload. See #1262."
    )


def test_the_environment_gate_mirrors_the_write_condition():
    """The property that keeps the gate correct rather than merely absent.

    `environment:` decides who waits for a human; "Publish to R2"'s `if:`
    decides who actually writes. Independently-written "equivalent"
    predicates are how the two quietly stop agreeing - so this asserts the
    write condition's exact text is embedded in the environment expression,
    not just something logically similar to it.
    """
    job = _job()
    write_condition = (_named(job["steps"], "Publish to R2").get("if") or "").strip()
    core = write_condition.removeprefix("${{").removesuffix("}}").strip()
    assert core, '"Publish to R2" has no if: condition to mirror'

    environment = job.get("environment") or ""
    assert core in environment, (
        f"the job's environment: {environment!r} does not contain \"Publish to R2\"'s own write "
        f"condition ({core!r}) verbatim. If the write condition changed on purpose, copy the new "
        "text into the environment expression too - see #1262."
    )


def test_a_run_that_writes_still_names_production():
    """The other half: the fix must narrow the gate, not remove it.
    expected-protections.yml's `production` entry and RELEASING.md §12 both
    depend on this exact string - it is what test_repository_protections.py
    looks up by name."""
    environment = _job().get("environment") or ""
    assert "'production'" in environment, (
        f"environment: {environment!r} no longer names 'production' anywhere - a run that reaches "
        "Publish to R2 must still wait for the maintainer. See RELEASING.md §12."
    )
