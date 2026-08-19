"""Nothing reaches extensions.duckdb.org to get the spatial extension (#321).

`INSTALL spatial` is a live network fetch, and TESTING.md names it as the one
standing exception to "tests never touch the network". Two consequences, and
the second is the one that bites hardest:

  - a DuckDB extension-repo outage reddens the pipeline suite for a reason
    that has nothing to do with the change under test, which is exactly the
    "red means the ecosystem's release calendar" #321 was filed against;
  - the web sandbox's proxy 403s that host outright, so the fetch cannot
    succeed there at all.

`pipeline/seed_spatial_extension.py` copies the build DuckDB publishes on PyPI
into the path INSTALL checks first. This suite holds the three places that
have to keep agreeing about it: the two CI jobs that run DuckDB code, and the
web-session hook.

WHY THE JOB LIST IS DERIVED RATHER THAN LISTED. #321 names only the four test
fixtures that call `INSTALL spatial`, and missed that `load_raw.py` calls it
too - so the *dbt* job pays the same fetch without any test mentioning it. A
hardcoded list of jobs would have inherited that blind spot. These tests ask
which jobs run DuckDB-touching entrypoints and require seeding of each, so a
new job that loads the warehouse is covered by construction.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pipeline-tests.yml"
HOOK = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"
SEEDER = REPO_ROOT / "pipeline" / "seed_spatial_extension.py"

SEEDER_NAME = "seed_spatial_extension.py"

# The commands that end up executing `INSTALL spatial`, and therefore need the
# extension already on disk. `pytest` reaches it through the fixtures in
# pipeline/tests; `load_raw.py` calls it directly (pipeline/load_raw.py).
NEEDS_SPATIAL = ("pytest", "load_raw.py")


def _jobs():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def _run_steps(job):
    return [step for step in job["steps"] if isinstance(step.get("run"), str)]


def _seed_index(job):
    for index, step in enumerate(_run_steps(job)):
        if SEEDER_NAME in step["run"]:
            return index
    return None


def _first_spatial_index(job):
    for index, step in enumerate(_run_steps(job)):
        if any(needle in step["run"] for needle in NEEDS_SPATIAL):
            return index
    return None


def _jobs_needing_spatial():
    return {name: job for name, job in _jobs().items() if _first_spatial_index(job) is not None}


def test_some_job_actually_runs_duckdb():
    """Guard on the guard: if the detection above stops matching anything, every
    other test in this file passes vacuously."""
    assert _jobs_needing_spatial(), f"no job in {WORKFLOW.name} appears to run {NEEDS_SPATIAL}"


@pytest.mark.parametrize("job_name", sorted(_jobs_needing_spatial()))
def test_every_job_that_runs_duckdb_seeds_the_extension_first(job_name):
    """Both jobs, and in the right order - seeding after the fetch has already
    been attempted would be a step that runs, reports success, and saves
    nothing."""
    job = _jobs_needing_spatial()[job_name]

    seed_at = _seed_index(job)
    assert seed_at is not None, f"job {job_name!r} runs DuckDB but never seeds the extension"
    assert seed_at < _first_spatial_index(job), f"job {job_name!r} seeds the extension after it is needed"


@pytest.mark.parametrize("job_name", sorted(_jobs_needing_spatial()))
def test_the_extension_version_is_taken_from_duckdb_itself(job_name):
    """Extensions are ABI-locked to the exact DuckDB build, so the version has
    to come from the installed interpreter rather than from a requirements
    file - the two agree only while nothing has overridden one of them, and
    the dbt job installs a different requirements set from the pytest job."""
    job = _jobs_needing_spatial()[job_name]
    seed_at = _seed_index(job)
    # Checked rather than indexed straight through: without this, a job that
    # has lost its seeding step entirely fails here with a TypeError about
    # list indices, which reads as a broken test rather than a missing step.
    assert seed_at is not None, f"job {job_name!r} runs DuckDB but never seeds the extension"
    seeding = _run_steps(job)[seed_at]["run"]

    assert "duckdb-extension-spatial" in seeding, f"job {job_name!r} never installs the extension package"
    assert "duckdb.__version__" in seeding, f"job {job_name!r} pins the extension from something other than the installed duckdb"


def test_the_seeder_exists_where_everything_points_at_it():
    assert SEEDER.is_file()


def test_the_hook_uses_the_same_script_rather_than_its_own_copy():
    """It was an inline heredoc in the hook until CI needed it too. Three
    copies of a path keyed by DuckDB's version and platform triple would drift
    on the next duckdb bump, which is the whole reason it moved to a file."""
    hook = HOOK.read_text()

    assert SEEDER_NAME in hook, "the session-start hook no longer calls the shared seeder"
    assert "PRAGMA platform" not in hook, "the hook has grown its own copy of the seeding logic again"


def test_the_seeder_proves_it_worked():
    """#822's lesson: a provisioning step that exits 0 without achieving
    anything is how both of this repository's silent dependency outages
    happened. Seeding into a path INSTALL ignores would look identical to
    success without this."""
    source = SEEDER.read_text()

    assert "INSTALL spatial; LOAD spatial;" in source
    assert "ST_Point" in source
