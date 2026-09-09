"""A `data_environment: ua` publish must not wait on the production reviewer (#1330).

THE GAP THIS FILE'S SUBJECT CLOSES

`migrate.yml` has always scoped its required-reviewer gate to a genuine production
dispatch - UA is applied "here first, always" (RELEASING.md §3), ungated, and only the
production leg (`needs: ua`) waits on a human. The four `publish` jobs that write map
data - publish-vector-data.yml, build-basemap.yml, build-dem.yml, build-raster.yml -
never made that distinction: `environment: production` sat on each one unconditionally,
so a routine `data_environment: ua` dispatch waited on the identical approval as an
actual production promotion. CLAUDE.md's own "dispatch each staled path with
data_environment: ua" instruction, followed after nearly every merge that stales a
pipeline path, was most of that approval traffic.

THE FIX, AND WHY IT IS SAFE FROM #1262'S FAILURE MODE

`environment:` on each of the four jobs is now
`${{ inputs.data_environment == 'production' && 'production' || inputs.data_environment }}`
- a same-job expression, which is exactly the shape #1262 got burned by once already.
What made that one a bug was not the expression shape, it was duplication: the
expression mirrored a *second, independently-written* copy of the same predicate (a
step's own `if:` inside the same job), and the two drifted out of sync. #1265's fix was
to make the job's own `if:` the only place the write/no-write question is answered, with
`environment:` unconditional inside it.

This expression asks a different question - which environment, not whether to write at
all - and nothing else in any of these four jobs branches on `data_environment` in YAML
(the actual behavioural difference lives inside publish.py, reached through the
OURHIKE_DATA_ENV environment variable). So there is no second, independently-written
copy of *this* predicate for it to drift from.

WHAT THIS DOES NOT CHANGE

A genuine `data_environment: production` dispatch, and migrate.yml's production job,
still resolve to the literal `production` environment and still wait on the reviewer
RELEASING.md §12 depends on - test_repository_protections.py's
test_the_production_environment_asks_a_human checks that live, unaffected by anything
here. Nothing in this file, or in the change it tests, touches
`.github/expected-protections.yml`'s required_reviewers_at_least or prevent_self_review.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"

# Every job that actually calls publish.py for a `data_environment` this
# repository takes as a workflow_dispatch choice. build-raster.yml's
# `disabled` switch (#855) gates whether this job ever starts, not what it
# does once it does - the same environment expression applies once
# `run_despite_withdrawal` is ticked, so the job stays in scope here rather
# than being excused.
PUBLISH_JOBS = {
    "publish-vector-data.yml": "publish",
    "build-basemap.yml": "publish",
    "build-dem.yml": "publish",
    "build-raster.yml": "publish",
}

EXPECTED_ENVIRONMENT = "${{ inputs.data_environment == 'production' && 'production' || inputs.data_environment }}"


def _job(filename: str, job_id: str) -> dict:
    workflow = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
    return workflow["jobs"][job_id]


def test_the_rule_has_something_to_check():
    """A rename or a refactor that moved one of these jobs would otherwise
    turn every assertion below into a pass over nothing - the vacuous-green
    idiom test_repository_settings.py and test_publish_concurrency.py both
    guard their own version of this against."""
    assert len(PUBLISH_JOBS) == 4


@pytest.mark.parametrize("filename,job_id", sorted(PUBLISH_JOBS.items()))
def test_environment_is_conditional_on_data_environment(filename, job_id):
    """The regression #1330 fixes, and the one #1330 could reintroduce in
    either direction: a `data_environment: ua` run must not park in
    `waiting` behind a reviewer for a write RELEASING.md §3b already calls
    disposable, and a `data_environment: production` run must still resolve
    to the literal 'production' string RELEASING.md §12 depends on.

    Asserted as an exact match rather than a substring, the same reasoning
    test_publish_dry_run_gate.py gives for its own exact-match assertion on
    this same field: a rewrite that keyed off some other input, or that
    stopped resolving to the literal 'production' string for a real
    production dispatch, would silently ungate an actual release."""
    environment = _job(filename, job_id).get("environment")
    assert environment == EXPECTED_ENVIRONMENT, (
        f"{filename}:{job_id}'s environment is {environment!r}, not the exact expression "
        f"{EXPECTED_ENVIRONMENT!r}. If this now reads the plain string 'production', every "
        "UA follow-up waits on the maintainer again (#1330). If it reads anything else, "
        "check by hand that a data_environment: production dispatch still resolves to the "
        "literal 'production' string - RELEASING.md §12's reviewer gate depends on that "
        "exact name."
    )
