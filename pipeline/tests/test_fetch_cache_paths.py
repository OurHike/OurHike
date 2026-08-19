"""The publish workflow's cache must carry every file a receipt names (#542).

WHY THIS EXISTS, WHICH IS A MISTAKE I MADE WRITING #542. The cache path list
in publish-vector-data.yml is hand-written, and I put elevation's tile index
under `data/processed/elevation/` in it. It lives in `data/raw/elevation/`.
Nothing would have caught that: the list is YAML, the paths are Python
constants, and the only place the two meet is a GitHub runner nobody watches
during a green run.

The consequence is the exact failure the receipt design is supposed to
prevent, arriving through the back door. A receipt records the hash of every
output its fetcher stands behind, and `check_output_quality.py` re-hashes
them. Restore the receipt without the file and the gate reports DRIFT - "this
changed since it was fetched" - when the truth is that a line in a YAML list
was wrong. That is a false alarm pointing at the data, on the check standing
in front of publish, which is the worst possible place to be misdirected.

So the list is asserted against the fetchers' own constants rather than
trusted. This is `verify_release.py`'s reasoning about parsing `config.ts`
one more time: the paths have one home, in the fetcher that writes them, and
anything else holding a copy has to be checked against it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import build_osm_water_reach
import fetch_all
import fetch_atc_photos
import fetch_elevation
import fetch_opentrail
import fetch_osm_water
import fetch_poi_images
import fetch_trail_water
from lib import fetch_receipts

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "pipeline"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-vector-data.yml"

#: Captured at import, before conftest's autouse fixture redirects it at a
#: tmp directory for every test in this suite. That fixture is right - nothing
#: should write receipts into the real tree - but this test is about the REAL
#: location, so it takes the value while it is still the real one.
REAL_RECEIPTS_DIR = fetch_receipts.receipts_dir()


def _fetch_all_outputs() -> list[Path]:
    """Every file `fetch_all.py`'s receipt names: the manifest, and one
    geojson per registered ArcGIS source.

    The keys are read from `sources.json` rather than assumed, because a
    fourteenth source whose name the glob did not match is precisely the kind
    of gap this file exists to find."""
    from lib.source_registry import arcgis_sources, load_registry

    registry = load_registry(fetch_all.SOURCES_PATH)
    sources = arcgis_sources(registry)
    if not sources:
        raise AssertionError("no ArcGIS sources found in sources.json - this test would assert nothing")
    return [fetch_all.MANIFEST_PATH] + [fetch_all.RAW_DIR / f"{src['key']}.geojson" for src in sources]


#: Each vector fetcher, and what its receipt stands behind. The paths come out
#: of the modules and the registry rather than being written down again here,
#: so moving one is caught rather than duplicated.
FETCHER_OUTPUTS = (
    ("fetch_all", _fetch_all_outputs),
    ("fetch_opentrail", lambda: [fetch_opentrail.OUT_PATH]),
    ("fetch_atc_photos", lambda: [fetch_atc_photos.OUT_PATH]),
    ("fetch_poi_images", lambda: [fetch_poi_images.OUT_PATH]),
    ("fetch_elevation", lambda: [fetch_elevation.INDEX_PATH]),
    # The scan's small output only - the multi-gigabyte state extracts it
    # reads are deliberately NOT cached (the workflow step says why), so an
    # unticked run restores the last scan's geojson rather than the inputs.
    ("fetch_osm_water", lambda: [fetch_osm_water.OUT_PATH]),
    # Not a fetcher - it derives rather than downloads - but it records a
    # receipt like one, so this list is exactly where it belongs (#818). It
    # was missing at first, and the shape of that miss is the shape this file
    # was written for: the reachability build landed with no workflow step at
    # all, so nothing cached its output, and nothing here noticed because the
    # roster is hand-kept. `fetch_receipts.record` is the thing that makes an
    # entry mandatory, not the word "fetch" in the module name.
    ("build_osm_water_reach", lambda: [build_osm_water_reach.OUT_PATH]),
    ("fetch_trail_water", lambda: [fetch_trail_water.OUT_PATH]),
)


@pytest.fixture(scope="module")
def cached_paths() -> list[str]:
    """The workflow's FETCH_OUTPUTS, as workspace-relative path strings."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    raw = workflow["jobs"]["build-and-publish"]["env"]["FETCH_OUTPUTS"]
    entries = [line.strip() for line in raw.splitlines() if line.strip()]
    if not entries:
        raise AssertionError(
            "FETCH_OUTPUTS is empty or has moved in publish-vector-data.yml. This test "
            "must be updated rather than left asserting nothing."
        )
    return entries


def _covered(relative: Path, cached: list[str]) -> bool:
    """Whether `relative` (from the repo root) is carried by some cache entry.

    Handles the three forms the list uses - an exact file, a glob, and a bare
    directory standing for everything under it - because `actions/cache`
    accepts all three and the point of this test is to model what the runner
    will really restore."""
    text = relative.as_posix()
    for entry in cached:
        if entry == text:
            return True
        if "*" in entry and Path(text).match(entry):
            return True
        if not entry.endswith("/") and text.startswith(entry.rstrip("/") + "/"):
            return True
    return False


@pytest.mark.parametrize(
    ("fetcher", "outputs"),
    FETCHER_OUTPUTS,
    ids=[name for name, _ in FETCHER_OUTPUTS],
)
def test_every_fetcher_output_is_carried_between_runs(fetcher, outputs, cached_paths):
    for path in outputs():
        relative = Path(path).relative_to(REPO_ROOT)

        assert _covered(relative, cached_paths), (
            f"{fetcher} writes {relative}, which no FETCH_OUTPUTS entry in "
            f"publish-vector-data.yml covers. A receipt restored without its output fails "
            f"check_output_quality.py's fetches check as drift. Entries: {cached_paths}"
        )


def test_the_receipts_themselves_are_carried(cached_paths):
    """The other half, and the one that makes the rest matter: without the
    receipts, every run looks like a run where nothing was ever fetched."""
    relative = REAL_RECEIPTS_DIR.relative_to(REPO_ROOT)

    assert _covered(relative, cached_paths), f"{relative} is not in FETCH_OUTPUTS"


def test_the_cache_is_restored_before_the_first_fetch_and_saved_after_the_last(cached_paths):
    """Order, because both ends are easy to get wrong and neither fails
    loudly. A restore below the first fetch would leave that fetch cold every
    run; a save above the last would carry everything except what the steps
    below it produced - which is exactly what the photo-only cache this
    replaced did to elevation."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    names = [step.get("name") or step.get("uses") for step in workflow["jobs"]["build-and-publish"]["steps"]]

    restore = names.index("Restore fetched data")
    save = names.index("Save fetched data")
    fetches = [i for i, name in enumerate(names) if name and name.startswith("Fetch ")]

    assert restore < min(fetches)
    assert save > max(fetches)


def test_the_save_runs_even_when_an_earlier_step_failed(cached_paths):
    """`actions/cache`'s bundled post-step is skipped on job failure, which is
    what threw away ~55 minutes of fetching on both failed runs of 2026-08-09.
    The split into restore/save exists for this one line, so the line is
    pinned."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    save = next(step for step in workflow["jobs"]["build-and-publish"]["steps"] if step.get("name") == "Save fetched data")

    assert "always()" in str(save.get("if", ""))


# --- The derived files also have a home in the bucket (#812) ------------------
#
# The cache list above answers "does this survive between runs?"; these answer
# "does it survive the cache being gone?". Both questions exist because
# data/raw/ is gitignored, so a derived file's only homes are the cache and R2.
#
# #812 is what happens with just the first: fetch_osm_water.py's scan,
# build_osm_water_reach.py's verdicts and fetch_trail_water.py's crossings were
# reachable only through an Actions cache that GitHub evicts after 7 days unread
# and caps at 10 GB against ~430 MB a run. Run 32258156317 missed it and
# restored in zero seconds. A miss does not fail - export_poi.read_sources()
# reads what is on disk - so the run publishes a map short ~1,100 crossings and
# every reachable spring, with nothing saying so. Since #825 those are live
# ledger rows too (1,247 of 4,230), so a miss also trips the mass-retirement
# refusal.

#: The derived files that must round-trip through the bucket rather than only
#: the cache. Deliberately not every sidecar: build_state.json is written by
#: check_freshness and the photo outcomes have their own restore step and their
#: own reason (#465).
DERIVED_SIDECARS = ("osm_water.geojson", "osm_water_reach.json", "trail_water.json")

RESTORE_STEP = "Restore derived water data from the published data"


@pytest.fixture(scope="module")
def workflow_steps() -> list[dict]:
    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return parsed["jobs"]["build-and-publish"]["steps"]


def _step_named(steps: list[dict], name: str) -> dict:
    for step in steps:
        if (step.get("name") or "") == name:
            return step
    raise AssertionError(f"no step named {name!r} - a rename must update this test with it")


def _step_index(steps: list[dict], name: str) -> int:
    return next(i for i, step in enumerate(steps) if (step.get("name") or "") == name)


@pytest.mark.parametrize("name", DERIVED_SIDECARS)
def test_the_derived_water_files_are_published_as_sidecars(name):
    """Without this they exist only in the cache, and a miss silently ships a
    map with no crossings and no reachable springs."""
    import publish

    assert name in publish.SIDECARS, (
        f"{name} is not in publish.SIDECARS, so it is never uploaded - its only home is an Actions cache that expires. See #812."
    )


@pytest.mark.parametrize("name", DERIVED_SIDECARS)
def test_every_derived_sidecar_is_restored_by_the_workflow(workflow_steps, name):
    """Uploading without restoring is half a mechanism: the bucket would hold a
    copy nothing ever reads back."""
    script = _step_named(workflow_steps, RESTORE_STEP).get("run") or ""
    assert name in script, f"{RESTORE_STEP!r} does not restore {name} - it would be published and never read back"


def test_the_restore_covers_exactly_the_derived_sidecars(workflow_steps):
    """Neither list may grow without the other. A file published but not
    restored is dead weight in the bucket; one restored but not published is a
    404 on every run."""
    import publish

    script = _step_named(workflow_steps, RESTORE_STEP).get("run") or ""
    restored = {name for name in publish.SIDECARS if name in script}
    assert restored == set(DERIVED_SIDECARS), (
        f"the restore step handles {sorted(restored)}, but this test expects {sorted(DERIVED_SIDECARS)} - "
        "add the new file to both publish.SIDECARS and the workflow step, or to this list"
    )


def test_the_restore_runs_before_anything_reads_those_files(workflow_steps):
    """Before the source preflight, which is the ordering that matters.

    `export_poi.py --check` REFUSES when osm_water.geojson has no
    osm_water_reach.json beside it (#818), so a half-filled pair is worse than
    an empty one - restoring after the preflight could hand it exactly that.
    The reach build downstream also resumes from osm_water_reach.json instead
    of re-running its EPQS pass, which only helps if the file is there first.
    """
    restore = _step_index(workflow_steps, RESTORE_STEP)
    for consumer in ("Check POI sources are exportable", "Build OSM water reachability", "Export POIs"):
        assert restore < _step_index(workflow_steps, consumer), (
            f"{RESTORE_STEP!r} runs after {consumer!r}, which reads the files it restores"
        )


def test_a_cache_hit_is_not_overwritten_by_the_restore(workflow_steps):
    """This fills gaps the cache left. The cached copy is the one this run's
    fetchers may already have refreshed, so clobbering it with the last
    PUBLISHED copy would quietly undo the work."""
    script = _step_named(workflow_steps, RESTORE_STEP).get("run") or ""
    assert "already present (cache hit)" in script, "the restore must skip files the cache already provided"
