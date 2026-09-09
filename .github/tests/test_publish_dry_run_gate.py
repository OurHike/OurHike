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

#1262'S FIX, AND WHAT #1265 DID TO IT

#1262 fixed this with `environment: ${{ (inputs.publish && ...) && 'production'
|| 'no-write' }}` on the one job build-and-publish shared - a same-job
predicate mirroring "Publish to R2"'s own `if:`, kept honest only by a test
asserting the two stayed textually identical, because two independently
written copies of one question is the drift this repository keeps finding.

#1265 split that job into `build` (writes nothing, needs no environment) and
`publish` (`needs: build`, gated by
`if: inputs.publish && !inputs.regenerate_identity_ledger`), which moves the
predicate to the one place it decides anything: whether the `publish` job
runs at all. `environment: production` on that job is unconditional now,
the same as build-basemap.yml's and build-dem.yml's publish jobs, because
the job's own `if:` already means it never runs without intent to write.
There is no second, independently-written copy of the predicate left for a
test to keep in sync with the first - the drift this file used to guard
against is now structurally impossible rather than merely caught.

WHAT IS ACTUALLY WORTH TESTING NOW

That the `publish` job's `if:` still names `inputs.publish` (the #1262 half
- test_identity_ledger_regeneration.py's test_a_regeneration_run_cannot_publish
holds the `regenerate_identity_ledger` half, since that file is where the
ledger's mutual-exclusion property is asserted end to end), that `publish`
still depends on `build` having run first, and that a run which does reach
`publish` still names an environment at all.

WHAT #1330 DID TO IT

Not the literal `production` string specifically, any more: a `data_environment: ua`
publish is the routine, disposable case (RELEASING.md §3b) and #1330 made
`environment:` conditional on `inputs.data_environment` so it stops waiting on the
reviewer too. That reintroduces the shape this file's #1262 section warns about - a
same-job `environment:` expression - but not the bug: #1262's failure was the
expression mirroring a *second, independently-written* copy of the write/no-write
predicate this job's own `if:` already answers, and #1330's expression answers a
different question (which environment) that has no second copy anywhere in this job
to drift from. Which exact value it resolves to for which input is
test_publish_data_environment_gating.py's property to hold - this file does not carry
a second copy of that exact string to keep in sync with the first.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish-vector-data.yml"


def _publish_job() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["publish"]


def test_the_publish_job_does_not_run_for_a_dry_run():
    """The regression #1262 fixes: a run with publish: false must not wait
    on the reviewer for something it structurally cannot upload."""
    condition = _publish_job().get("if") or ""
    assert "inputs.publish" in condition, (
        f"the 'publish' job's if: {condition!r} no longer names inputs.publish - a dry run would "
        "run this job (and wait on the reviewer below) for nothing it could ever upload. See #1262."
    )


def test_the_publish_job_still_needs_the_build_job():
    """`publish` reads what `build` wrote via the vector-data-build-output
    artifact (#1265) - without `needs: build`, GitHub Actions is free to run
    the two in either order, or in parallel, and download an artifact that
    does not exist yet."""
    assert _publish_job().get("needs") == "build", (
        "the 'publish' job no longer declares needs: build - it would be free to start before the "
        "build job has uploaded anything for it to download. See #1265."
    )


def test_a_run_that_reaches_publish_still_names_an_environment():
    """RELEASING.md §12 - only the maintainer ships - depends on a run that
    writes still naming an environment at all. #1330 split which exact value
    that is into its own home, test_publish_data_environment_gating.py, so
    this file only checks that the field survived rather than holding a
    second copy of the exact expression to keep in sync with the first."""
    environment = _publish_job().get("environment")
    assert environment, (
        "the 'publish' job no longer names an environment at all - a run that writes to "
        "the bucket must still be able to wait for the maintainer. See RELEASING.md §12 and "
        "test_publish_data_environment_gating.py for which environment it resolves to."
    )
