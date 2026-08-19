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

AND WHERE THOSE STEPS SIT (#816)

The second half of this file holds the ordering, which is a separate property
that the first half quietly depends on. Reconciliation reads
`data/raw/osm_water.geojson` and `data/raw/trail_water.json`; both are restored
from the Actions cache at the top of the job and rewritten by fetchers partway
down. An identity step placed above those fetchers therefore judges the
PREVIOUS run's water while `Export POIs` publishes this one's - so `--check`
can pass on a snapshot nobody ships, and a regenerated ledger can be stale the
moment it is uploaded. features/POI_IDENTITY.md §2 always said "after the
fetches"; the workflow only partly agreed until #816.

AND WHETHER THE ARTIFACT MEANS ANYTHING (#818, #819)

The last two sections are the same lesson arriving twice more in one day, which
is why they live here rather than in files of their own.

#819: the upload leaned on `if-no-files-found: ignore` to stay quiet when
reconciliation wrote nothing. `reference/poi_identity.json` is checked in, so
that case never existed, and a job dying early still shipped the committed file
labelled as a regenerated one - an empty diff that reads as "nothing changed"
when the truth is "nothing ran".

#818: `export_poi.read_sources()` refuses to run when `osm_water.geojson` has no
`osm_water_reach.json` beside it, and no step built one, so every dispatch died
at the preflight. A gate shipped without the thing that satisfies it - the same
sentence as #811 above, about a different gate, three PRs later. These tests are
the cheap way to notice the next one.
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


# --- Ordering: the gate must judge the data the export will publish (#816) ---


WATER_FETCH_STEPS = ("Fetch OSM water points", "Derive trail water")

IDENTITY_STEPS = (
    "Check the POI identity ledger is current",
    "Reconcile the POI identity ledger for review",
)


def _position(steps: list[dict], name: str) -> int:
    for index, step in enumerate(steps):
        if (step.get("name") or "") == name:
            return index
    raise AssertionError(f"no step named {name!r} - this test names steps exactly, so a rename must update it")


@pytest.mark.parametrize("identity_step", IDENTITY_STEPS)
@pytest.mark.parametrize("fetch_step", WATER_FETCH_STEPS)
def test_identity_reconciles_after_the_sources_it_reads(steps, identity_step, fetch_step):
    """`published_records()` reads `data/raw/osm_water.geojson` and
    `data/raw/trail_water.json` through `export_poi.read_sources()`. Both are
    written by the steps below and restored from the Actions cache before them,
    so an identity step ordered FIRST reconciles the previous run's water while
    `Export POIs` publishes this run's - the gate passing judgement on a
    snapshot nobody ships.

    Observed on run 32254119619 before the fix: the ledger artifact was
    uploaded at 12:46:11, `Fetch OSM water points` ran until 12:51:45, and
    `Derive trail water` had not started.
    """
    assert _position(steps, identity_step) > _position(steps, fetch_step), (
        f"{identity_step!r} runs before {fetch_step!r}, so it reconciles whatever the cache "
        "restored rather than what this run derived. See #816."
    )


def test_identity_still_settles_before_anything_is_exported(steps):
    """The other half of the sandwich: the gate is worth nothing after the
    artifacts it gates are already written. #659 moved the export's own
    emptiness check before its write loop for the same reason."""
    last_identity = max(_position(steps, name) for name in IDENTITY_STEPS)
    for export_step in ("Export trail lines", "Export POIs"):
        assert last_identity < _position(steps, export_step), (
            f"{export_step!r} runs before the identity gate settles - POIs would be written under ids nothing had checked."
        )


def test_the_cheap_preflight_stays_cheap(steps):
    """Moving identity down must not drag the seconds-long source check with
    it. `export_poi.py --check` is what still catches an unreadable source
    before an hour of fetching, and #816 traded away the identity verdict's
    earliness on the explicit basis that this one keeps its own."""
    preflight = _position(steps, "Check POI sources are exportable")
    for fetch_step in WATER_FETCH_STEPS:
        assert preflight < _position(steps, fetch_step), (
            "'Check POI sources are exportable' must stay ahead of the expensive fetches - it is "
            "the fast failure the identity gate no longer provides."
        )


# --- The artifact must not be a phantom (#819) --------------------------------


def test_the_upload_is_gated_on_reconciliation_having_actually_run(steps):
    """`always()` alone uploads the COMMITTED ledger when reconciliation never
    ran, and calls it `poi-identity-ledger`.

    `reference/poi_identity.json` is checked in, so it is on disk from the
    moment `actions/checkout` finishes; `if-no-files-found: ignore` therefore
    has no case to catch and never fires. Run 32255950280 died at the source
    preflight (#818), skipped reconciliation, and still produced an artifact
    byte-identical to the file already in the tree - an empty diff whose
    natural reading ("reconciliation found no changes") was the exact opposite
    of the truth.
    """
    reconcile = _named(steps, "Reconcile the POI identity ledger")
    assert reconcile.get("id"), "the upload gates on this step's outcome, so it needs an id"

    upload = _named(steps, "Upload the reconciled ledger")
    condition = upload.get("if") or ""
    assert f"steps.{reconcile['id']}.outcome" in condition, (
        f"'Upload the reconciled ledger for review' is guarded by {condition!r}, which does not "
        "check whether reconciliation ran. On a job that fails earlier it will upload the "
        "committed ledger and present it as a regenerated one. See #819."
    )
    assert "always()" in condition, (
        "still needs always(): an exit-2 hold writes no ledger but DOES print the held list, "
        "which is the entire reason a human was called"
    )


# --- The reachability gate has to be feedable (#818) --------------------------


def test_something_builds_the_osm_reachability_verdicts(steps):
    """`export_poi.read_sources()` refuses to run when `osm_water.geojson` is
    present without `osm_water_reach.json`. That refusal is correct - the
    alternatives are publishing every corridor point ungated or dropping the
    source silently - but it means the workflow has to produce the file, and
    for a while nothing did: every dispatch died twelve seconds in at the
    preflight (run 32255950280)."""
    build = _named(steps, "Build OSM water reachability")
    assert "build_osm_water_reach.py" in (build.get("run") or "")
    assert _position(steps, "Build OSM water reachability") > _position(steps, "Fetch OSM water points"), (
        "the reach build measures the points fetch_osm_water.py writes, so a fresh fetch must land before it"
    )
    assert _position(steps, "Build OSM water reachability") < _position(steps, "Export POIs"), (
        "export_poi.py is the consumer that refuses without the verdicts"
    )


def test_the_reachability_build_is_not_gated_on_the_fetch_input(steps):
    """The subtlety that made #818 possible in the first place.

    `export_poi.py`'s trigger is *`osm_water.geojson` exists*, not *this run
    fetched it* - and that file rides `FETCH_OUTPUTS` through the `*.geojson`
    glob, so a run with `include_osm_water` unticked still restores it from the
    cache and still needs the verdicts. Gating this step on the input would
    leave exactly that path broken, and it is the path the failing run was on.
    """
    build = _named(steps, "Build OSM water reachability")
    assert "include_osm_water" not in (build.get("if") or ""), (
        "gating the reach build on include_osm_water re-breaks the unticked path, where "
        "osm_water.geojson comes back from the cache and export_poi.py still demands verdicts"
    )
    assert "osm_water.geojson" in (build.get("run") or ""), (
        "the step should test for the file itself - the same predicate export_poi.py applies - "
        "so the two cannot drift into disagreeing about when the build is required"
    )
