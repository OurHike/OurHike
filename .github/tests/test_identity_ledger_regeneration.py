"""A run that rewrites the POI identity ledger cannot also publish it (#811).

THE GAP THIS FILE'S SUBJECT CLOSES

`publish-vector-data.yml` gates every publish on
`reconcile_poi_identity.py --check`: the checked-in ledger must be exactly what
reconciliation reproduces from the run's snapshot. When it differs, the step
fails with "run reconcile_poi_identity.py, review the diff, and commit it".

Nobody could. The script reads its snapshot through `export_poi.read_sources()`,
which reads `pipeline/data/raw/` - gitignored, and populated only on a runner
mid-job - and `--check` was the sole invocation anywhere under `.github/`. The
one environment that could produce the regenerated ledger was also the only one
that refused to. features/POI_IDENTITY.md §2 had specified the write path from
the start ("Output: the updated ledger and a human-readable summary"); what
shipped was its gate alone. Five consecutive dispatches failed on 2026-08-18/19
with no way forward.

WHAT IS ACTUALLY WORTH TESTING ABOUT THE FIX

Not that the input exists - that is one line of YAML and reads as its own
documentation. The property worth holding is the one a future edit could
plausibly undo by accident:

**a ledger that has just been rewritten is a ledger nobody has reviewed**, and
publishing from that run would put POIs into the bucket under ids whose diff no
human has read. That is precisely the failure #671 built the ledger to make
impossible, so `regenerate_identity_ledger` and `publish` are mutually exclusive
in the workflow rather than merely discouraged in the dispatch form.

The two modes being mutually exclusive with each other matters for the same
reason in reverse: a run that both `--check`s and rewrites would be asserting
and mutating the same file in one job, and which one won would depend on step
order.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-vector-data.yml"

REGENERATE_INPUT = "regenerate_identity_ledger"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def steps(workflow) -> list[dict]:
    return workflow["jobs"]["build-and-publish"]["steps"]


def _named(steps: list[dict], fragment: str) -> dict:
    """The one step whose name contains `fragment`, or a failure naming what
    was there instead - a renamed step must not slip through as a vacuous pass."""
    matches = [step for step in steps if fragment.lower() in (step.get("name") or "").lower()]
    assert len(matches) == 1, f"expected exactly one step matching {fragment!r}, found {[s.get('name') for s in matches]}"
    return matches[0]


def test_the_dispatch_form_offers_the_write_path(workflow):
    """Without this input there is no way to act on the gate's own instruction."""
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert REGENERATE_INPUT in inputs, (
        f"{REGENERATE_INPUT} is gone - the identity gate tells a maintainer to regenerate the "
        "ledger, and this input is the only thing in the repository that can. See #811."
    )
    assert inputs[REGENERATE_INPUT]["default"] is False, "regeneration is the exception, not the default posture of a publish run"


def test_the_write_mode_runs_reconcile_without_check(steps):
    """`--check` writes nothing by construction, so a regeneration step that
    carried the flag would upload the ledger it was asked to replace."""
    step = _named(steps, "Reconcile the POI identity ledger")
    run = step.get("run") or ""
    assert "reconcile_poi_identity.py" in run
    assert "--check" not in run, "the regeneration step must run the WRITE mode; --check writes nothing"
    assert step.get("if") == f"inputs.{REGENERATE_INPUT}"


def test_the_check_and_the_write_never_run_in_the_same_job(steps):
    """One job asserting a file and rewriting it would resolve by step order."""
    check = _named(steps, "Check the POI identity ledger is current")
    assert check.get("if") == f"${{{{ !inputs.{REGENERATE_INPUT} }}}}", (
        "the --check gate must be skipped on a regeneration run - otherwise the run fails on "
        "exactly the difference it was dispatched to resolve, and never reaches the write step"
    )


def test_a_regeneration_run_cannot_publish(steps):
    """The property this file exists for.

    A rewritten ledger is an unreviewed ledger. Publishing from that run ships
    POIs under ids whose diff no human has read - the silent orphaning #671
    exists to prevent, arriving through the door built to prevent it.
    """
    step = _named(steps, "Publish to R2")
    condition = step.get("if") or ""
    assert REGENERATE_INPUT in condition and "!" in condition, (
        f"'Publish to R2' is guarded by {condition!r}, which does not exclude a regeneration run. "
        "A run that has just rewritten the ledger has rewritten it to something nobody has "
        "reviewed; publishing from it defeats the identity gate entirely. See #811."
    )


def test_the_ledger_is_uploaded_even_when_reconciliation_refuses(steps):
    """`reconcile_poi_identity.py` exits 2 for held items and for the
    mass-retirement refusal, writing nothing. Those are the runs a human was
    called for, and the printed summary is the whole reason - so the upload
    runs on `always()` and tolerates the absent ledger rather than losing it."""
    step = _named(steps, "Upload the reconciled ledger")
    condition = step.get("if") or ""
    assert "always()" in condition, "an exit-2 run must still hand over the held-for-review list it printed"
    assert REGENERATE_INPUT in condition, "always() alone would upload on every ordinary publish run too"
    assert step["with"]["if-no-files-found"] == "ignore", "a held run writes no ledger; that is not an upload failure"
