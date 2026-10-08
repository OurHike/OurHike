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

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCOPES = REPO_ROOT / "scripts" / "pipeline_scopes.py"

#: The publishing paths that exist today. The script derives the roster from
#: which workflows invoke publish.py; this pins that the derivation finds
#: exactly these, so a rename or a refactor that drops one out of the
#: report fails here instead of silently shrinking the answer - and a
#: workflow that only MENTIONS the publisher fails here instead of being
#: handed dispatch advice for inputs it does not have (#1552). A real sixth
#: publisher belongs in this set, in the same pull request that adds it.
PUBLISHING_PATHS = {
    "build-basemap.yml",
    "build-dem.yml",
    "build-raster.yml",
    "publish-conditions.yml",
    "publish-vector-data.yml",
    # The sixth, from #1666 (features/WEATHER.md): its `publish` job runs
    # `python publish.py` on its own schedule. Found by this set becoming
    # exact (#1552). Under "at least these five" it had joined the roster on
    # main without anyone writing it down here.
    "publish-weather.yml",
    # The seventh, from #1793's monthly lane (pipeline/ELT.md, "Workflows").
    # Since the maintainer's choice B (2026-10-08) it extracts and pins, and
    # publishes through the eighth, which its dispatch job starts with
    # `gh workflow run build-reference.yml` (the derivation's dispatch rule).
    "refresh-reference.yml",
    # The eighth: the monthly lane's build from a pin, whose `publish` job runs
    # `python publish.py` with OURHIKE_PHONE_FILES=dbt.
    "build-reference.yml",
}

#: The extract paths: workflows that run `python -m extract._run` and no
#: publish.py, whose raw tables a publishing path reads later. Pinned exactly,
#: as the publishing roster is.
EXTRACT_PATHS = {
    # Decision 61's notices legs, every 4 hours; publish-conditions.yml's
    # hourly dbt path reads their served copy (pipeline/ELT.md, phase F).
    "extract-notices.yml",
}


def _load_scopes_module():
    spec = importlib.util.spec_from_file_location("pipeline_scopes", SCOPES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    lines = [line.split() for line in scopes.splitlines() if line.strip()]
    named = {line[0] for line in lines} - {"every-path", "extract-path"}
    assert PUBLISHING_PATHS <= named, f"derivation lost a publishing path: {sorted(PUBLISHING_PATHS - named)}"
    assert named <= PUBLISHING_PATHS, f"derivation invented a publishing path: {sorted(named - PUBLISHING_PATHS)}"
    assert {line[1] for line in lines if line[0] == "extract-path"} == EXTRACT_PATHS


def test_a_notices_source_stales_the_extract_path_that_lands_it_and_needs_no_dispatch():
    """A club's closures file is read by extract-notices.yml (an hourly type, extract/_contract.py's
    CADENCE_BY_TYPE), whose schedule reruns it from main; publishing paths do not claim it yet, so it is still
    named unclaimed for them rather than read as fresh."""
    verdict = _verdict(["pipeline/extract/usfs/closures.py"])
    assert "STALE  extract-notices.yml" in verdict
    assert "nothing to dispatch" in _note_after(verdict, "extract-notices.yml")
    assert "unclaimed  pipeline/extract/usfs/closures.py" in verdict


def test_a_monthly_types_club_file_leaves_the_extract_path_fresh():
    verdict = _verdict(["pipeline/extract/usfs/trail_lines.py"])
    assert "fresh  extract-notices.yml" in verdict


def test_the_extract_package_and_what_it_imports_stale_the_extract_path():
    for changed in ("pipeline/extract/_run.py", "pipeline/lib/arcgis.py", "pipeline/requirements-extract.txt"):
        assert "STALE  extract-notices.yml" in _verdict([changed]), changed


def test_a_shared_folders_file_of_an_hourly_type_stales_the_extract_path_and_a_monthly_one_does_not():
    """A _shared/ file names its type in `TYPE = "<type>"`, not by its own name."""
    assert "STALE  extract-notices.yml" in _verdict(["pipeline/extract/_shared/nifc/perimeters.py"])
    assert "fresh  extract-notices.yml" in _verdict(["pipeline/extract/_shared/ourhike/highlights.py"])


def test_a_monthly_types_extract_file_stales_the_publishing_path_that_runs_the_monthly_lane():
    """refresh-reference.yml runs `-m extract._run --lane monthly` and publishes, through build-reference.yml, what dbt
    builds from it, so the files of the types that lane carries are its scope, OSM's Geofabrik extracts (#1652) among
    them, while an hourly type's file stays outside it."""
    for changed in (
        "pipeline/extract/_shared/osm/geofabrik.py",
        "pipeline/extract/_geofabrik.py",
        "pipeline/extract/usfs/trail_lines.py",
        "pipeline/extract/_shared/ourhike/highlights.py",
    ):
        verdict = _verdict([changed])
        assert "STALE  refresh-reference.yml" in verdict, changed
        assert f"unclaimed  {changed}" not in verdict, changed
    assert "fresh  refresh-reference.yml" in _verdict(["pipeline/extract/usfs/closures.py"])
    assert "fresh  refresh-reference.yml" in _verdict(["pipeline/extract/_shared/nifc/perimeters.py"])
    # publish-conditions.yml's monthly-lane run reads the registry alone (`--only`), which is not the lane.
    assert "fresh  publish-conditions.yml" in _verdict(["pipeline/extract/_shared/osm/geofabrik.py"])


def test_a_step_build_marts_runs_stales_every_path_that_runs_build_marts():
    """build_marts.py starts each step as a subprocess by its STEPS entry's script name, which no import reaches, so
    step_osm_water.py was unclaimed though the monthly build lands OSM water through it (#1652). The monthly build is
    build-reference.yml's since choice B, and refresh-reference.yml reruns it through the dispatch."""
    verdict = _verdict(["pipeline/step_osm_water.py"])
    assert "STALE  build-reference.yml" in verdict and "STALE  publish-conditions.yml" in verdict
    assert "STALE  refresh-reference.yml" in verdict
    assert "unclaimed  pipeline/step_osm_water.py" not in verdict
    assert "fresh  build-dem.yml" in verdict


def test_a_workflow_that_dispatches_a_publishing_path_is_one_and_its_scope_holds_the_dispatched_ones():
    """Choice B (2026-10-08): refresh-reference.yml publishes nothing itself, and starts build-reference.yml with
    `gh workflow run`. Derived from the run scripts, so it stays a publishing path rather than turning into an
    extract path, and a run of it reruns everything the build reads."""
    scopes = _load_scopes_module()
    refresh = scopes.WORKFLOWS / "refresh-reference.yml"
    build = scopes.WORKFLOWS / "build-reference.yml"

    assert scopes.dispatched(refresh) == [build] and scopes.dispatched(build) == []
    assert not scopes.INVOKES_PUBLISH_RE.search(scopes.run_scripts(refresh)), "the publish is build-reference.yml's"
    assert refresh in scopes.publishing_workflows() and refresh not in scopes.extract_paths()
    assert scopes.scope_for(build) <= scopes.scope_for(refresh)


def test_a_change_to_what_the_pin_holds_stales_the_extract_and_pin_and_not_a_rebuild_from_an_old_pin():
    """build-reference.yml builds from a pin that exists, so a change to a scanner only the pin job runs, or to a
    monthly extract file, reaches hikers only through a new pin: refresh-reference.yml's path, not a dispatch of the
    build. (A script both halves read, such as fetch_trail_water.py, stales both, the conservative direction.)"""
    for changed in ("pipeline/fetch_osm_water.py", "pipeline/extract/_shared/osm/geofabrik.py"):
        verdict = _verdict([changed])
        assert "STALE  refresh-reference.yml" in verdict and "fresh  build-reference.yml" in verdict, changed


def test_the_dispatched_build_s_note_names_its_scheduled_caller_and_its_own_input_never_a_data_environment():
    """#1552 - A comment naming publish.py makes a workflow count as a publishing path - ended in dispatch advice for
    inputs a workflow does not have. build-reference.yml's only input is `raw_run`, read from its workflow_dispatch
    block, and refresh-reference.yml's schedule is what reruns it."""
    note = _note_after(_verdict(["pipeline/lib/data_env.py"]), "build-reference.yml")

    assert "refresh-reference.yml's schedule" in note
    assert "gh workflow run build-reference.yml --ref main -f raw_run=<raw_run>" in note
    assert "data_environment" not in note and "publish=true" not in note


def test_workflows_that_only_mention_the_publisher_are_not_publishing_paths():
    """#1552. Both of these explain in a comment why they do not publish, and
    matching the whole file's text counted that explanation as a publish -
    the recovery workflow's dispatch was then refused on 2026-09-23 for the
    two inputs pipelines.sh told the session to set."""
    verdict = _verdict(["pipeline/lib/data_env.py"])
    assert "nynjtc-archive-recovery.yml" not in verdict
    assert "propose-atc-updates.yml" not in verdict


def test_only_a_run_script_that_invokes_the_publisher_counts(tmp_path):
    scopes = _load_scopes_module()

    def publishes(workflow_yaml: str) -> bool:
        path = tmp_path / "candidate.yml"
        path.write_text(workflow_yaml)
        return bool(scopes.INVOKES_PUBLISH_RE.search(scopes.run_scripts(path)))

    invoked = "jobs:\n  publish:\n    steps:\n      - run: cd pipeline && python publish.py\n"
    assert publishes(invoked)
    assert publishes(invoked.replace("python publish.py", "python3 pipeline/publish.py"))
    assert publishes(invoked.replace("python publish.py", "python -m publish"))

    commented = "# publish.py is not run here\njobs:\n  a:\n    steps:\n      - run: python other.py\n"
    assert not publishes(commented)
    shell_comment = "jobs:\n  a:\n    steps:\n      - run: |\n          # then python publish.py\n          true\n"
    assert not publishes(shell_comment)
    echoed = 'jobs:\n  a:\n    steps:\n      - run: echo "publish.py did not succeed"\n'
    assert not publishes(echoed)
    step_name = "jobs:\n  a:\n    steps:\n      - name: before publish.py\n        uses: actions/checkout@v4\n"
    assert not publishes(step_name)


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
    """pipeline/reference/ is data with no import graph for the closure to
    walk, so it stays a blanket SHARED_ROOTS entry rather than joining
    pipeline/lib/ in the closure (#1624)."""
    verdict = _verdict(["pipeline/reference/anything_at_all.json"])
    for workflow in PUBLISHING_PATHS:
        assert f"STALE  {workflow}" in verdict, f"{workflow} did not go stale on a reference/ change"


def test_a_lib_module_every_path_imports_stales_every_path():
    """publish.py imports lib.data_env directly, and every publishing path's
    text names publish.py - so this is a real edge, not SHARED_ROOTS, and it
    reaches every path the same way #1624's fix means a narrower lib/ change
    should not."""
    verdict = _verdict(["pipeline/lib/data_env.py"])
    for workflow in PUBLISHING_PATHS:
        assert f"STALE  {workflow}" in verdict, f"{workflow} did not go stale on a lib/data_env.py change"


def test_a_lib_module_only_one_path_imports_stales_only_that_path():
    """#1624. pipeline/lib/work_projects.py is imported by export_work_projects.py
    alone, which only publish-conditions.yml runs - so a change to it must not
    stale build-dem.yml, which is what cost two 26-minute DEM builds nothing
    on 2026-09-23 when pipeline/lib/ was still a blanket SHARED_ROOTS entry."""
    verdict = _verdict(["pipeline/lib/work_projects.py"])
    assert "STALE  publish-conditions.yml" in verdict
    assert "fresh  build-dem.yml" in verdict
    assert "fresh  build-basemap.yml" in verdict
    assert "fresh  build-raster.yml" in verdict
    assert "fresh  publish-vector-data.yml" in verdict


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
    verdict = _verdict(["pipeline/lib/data_env.py"])
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
    verdict = _verdict(["pipeline/lib/data_env.py"])
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
