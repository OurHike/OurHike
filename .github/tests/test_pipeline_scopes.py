"""The publish-staleness answer stays derivable, and answers the known cases (#1123).

scripts/pipeline_scopes.py tells a session which publishing workflows a
diff stales, so the rerun a merged pipeline change needs stops depending on
the session that knew about it still being alive. Its scopes are DERIVED
from the workflow files - which scripts each invokes, plus the transitive
import closure over pipeline/ - so these tests hold the derivation's
contract rather than a copied path list:

- the roster of publishing paths is found, not remembered;
- a change reaches the workflows that run it, directly or through an
  import a workflow never names;
- the answer for a file the model cannot place is "unclaimed", said out
  loud, never a silent "fresh".

Driven as a subprocess on the real repository state, like
test_dev_scripts.py drives suite_scopes.py: the scopes exist only as a
reading of this checkout's workflows, so a synthetic fixture would test
the fixture.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCOPES = REPO_ROOT / "scripts" / "pipeline_scopes.py"

#: The publishing paths that exist today. The script derives the roster from
#: which workflows invoke publish.py; this pins that the derivation keeps
#: finding all five, so a rename or a refactor that drops one out of the
#: report fails here instead of silently shrinking the answer.
PUBLISHING_PATHS = {
    "build-basemap.yml",
    "build-dem.yml",
    "build-raster.yml",
    "publish-conditions.yml",
    "publish-vector-data.yml",
}


def _verdict(changed: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, str(SCOPES), "--changed"],
        input="\n".join(changed) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _note_after(verdict: str, workflow: str) -> str:
    """The action line printed directly under a workflow's STALE line."""
    lines = verdict.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"STALE  {workflow}"):
            return lines[i + 1]
    raise AssertionError(f"{workflow} is not STALE in:\n{verdict}")


def test_the_roster_is_derived_and_complete():
    scopes = subprocess.run(
        [sys.executable, str(SCOPES)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    named = {line.split()[0] for line in scopes.splitlines() if line.strip()}
    assert PUBLISHING_PATHS <= named, f"derivation lost a publishing path: {sorted(PUBLISHING_PATHS - named)}"


def test_an_exporter_stales_the_path_that_runs_it_and_only_that_path():
    verdict = _verdict(["pipeline/export_poi.py"])
    assert "STALE  publish-vector-data.yml" in verdict
    assert "fresh  build-dem.yml" in verdict
    assert "fresh  build-basemap.yml" in verdict


def test_an_import_stales_the_workflow_that_never_names_it():
    """export_dem.py does `from export_basemap import load_corridor_4326`,
    so a change to export_basemap.py stales the DEM build - the edge the
    filename-mention rule alone misses, and the reason the closure exists.
    If this fails because that import went away, pick another real edge
    rather than deleting the test: the mechanism is the thing under test."""
    verdict = _verdict(["pipeline/export_basemap.py"])
    assert "STALE  build-dem.yml" in verdict


def test_a_shared_root_stales_every_path():
    verdict = _verdict(["pipeline/lib/anything_at_all.py"])
    for workflow in PUBLISHING_PATHS:
        assert f"STALE  {workflow}" in verdict, f"{workflow} did not go stale on a lib/ change"


def test_tests_and_prose_stale_nothing():
    verdict = _verdict(["pipeline/tests/test_export_poi.py", "pipeline/WATER_SOURCES.md", "client/src/App.tsx"])
    assert "STALE" not in verdict
    assert "unclaimed" not in verdict


def test_a_file_the_model_cannot_place_is_unclaimed_not_fresh():
    verdict = _verdict(["pipeline/spike_day_planner.py"])
    assert "unclaimed  pipeline/spike_day_planner.py" in verdict


def test_the_self_healing_and_withdrawn_paths_say_so():
    """A stale conditions publish needs no dispatch (its schedule reruns it
    from main), and a stale raster build is #855's deliberate withdrawal -
    both read out of the workflow files, so flipping either behaviour there
    changes this answer in the same edit."""
    verdict = _verdict(["pipeline/lib/anything_at_all.py"])
    assert "nothing to dispatch" in _note_after(verdict, "publish-conditions.yml")
    assert "withdrawn" in _note_after(verdict, "build-raster.yml")
    assert "data_environment=ua" in _note_after(verdict, "publish-vector-data.yml")


def test_a_variant_taking_path_says_it_is_one_dispatch_per_variant():
    """#1147. Since #1088 `build-dem.yml` builds one artifact per `variant`,
    so a single dispatch refreshes `dem.pmtiles` and leaves `dem_light.pmtiles`
    at its last build - quietly, because an aged artifact is not a missing one
    and nothing 404s. Read from the workflow's own input rather than keyed on
    the file's name, so a second variant-taking path answers correctly with no
    edit here."""
    verdict = _verdict(["pipeline/lib/anything_at_all.py"])
    dem = _note_after(verdict, "build-dem.yml")

    assert "ONCE PER VARIANT" in dem
    assert "canonical" in dem and "light" in dem
    # And a path with no variant input says nothing about variants, so the
    # sentence stays a signal rather than boilerplate on every line.
    assert "ONCE PER VARIANT" not in _note_after(verdict, "build-basemap.yml")


def test_a_migration_gets_its_own_line():
    verdict = _verdict(["backend/alembic/versions/0042_widen_reports.py"])
    assert "migrations" in verdict
    assert "migrate.yml" in verdict


def test_the_unknown_flag_is_an_error_not_an_empty_answer():
    result = subprocess.run(
        [sys.executable, str(SCOPES), "--typo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "usage" in result.stderr
