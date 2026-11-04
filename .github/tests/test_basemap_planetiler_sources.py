"""build-basemap.yml keeps Planetiler's profile sources between runs (#1970).

Runs 57 and 58 (2026-11-03) both died 12 to 19 minutes in, inside a fixed
10-second wait Planetiler makes on osmdata.openstreetmap.de for the water
polygons' size whenever the file is missing. The fix is three steps in the
build job, and each test below holds one way of quietly undoing it:

- the restore and the fetch after the build, which puts the wait back after
  the state extracts;
- a restore key that has to match exactly, which turns every run cold;
- a save that is skipped after a partial fetch, which loses the files that
  did arrive, or one that can fail the run over a cache-service hiccup.

The cached path must be the directory lib/planetiler_sources.py's
SOURCES_DIR names; pipeline/tests/test_planetiler_sources.py holds that half.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "build-basemap.yml"
CACHED = "pipeline/data/sources"
PREFIX = "basemap-planetiler-sources-v1-"

RESTORE = "Restore Planetiler's profile sources"
FETCH = "Fetch Planetiler's profile sources that are missing or stale"
SAVE = "Save Planetiler's profile sources"
BUILD = "Build the basemap"


def _steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["build"]["steps"]


def _at(steps: list[dict], name: str) -> int:
    matches = [i for i, step in enumerate(steps) if step.get("name") == name]
    assert len(matches) == 1, f"expected exactly one step named {name!r}, found {len(matches)}"
    return matches[0]


def test_the_sources_are_restored_then_fetched_then_saved_all_before_the_build():
    steps = _steps()
    assert _at(steps, RESTORE) < _at(steps, FETCH) < _at(steps, SAVE) < _at(steps, BUILD)


def test_the_fetch_is_the_script_that_writes_the_save_marker():
    fetch = _steps()[_at(_steps(), FETCH)]
    assert fetch["run"].strip() == "python fetch_planetiler_sources.py"
    assert fetch["id"] == "planetiler_sources"


def test_the_restore_never_needs_an_exact_match():
    """A primary key unique to the run never matches, so restore-keys hands
    back the newest saved set. A fixed key would also restore, but would
    then keep its first save forever, because a cache key is written once."""
    restore = _steps()[_at(_steps(), RESTORE)]
    assert restore["uses"].startswith("actions/cache/restore@")
    assert restore["with"]["path"] == CACHED
    assert restore["with"]["restore-keys"] == PREFIX
    assert restore["with"]["key"] == PREFIX + "${{ github.run_id }}"


def test_the_save_follows_a_partial_fetch_only_when_something_landed_and_cannot_fail_the_run():
    """Keyed on the manifest lib/planetiler_sources.py writes beside the
    files, which changes exactly when a source is fetched.
    test_cache_keys_are_content_addressed.py holds the general rule (a
    content-addressed key, guarded on the files it hashes); this holds that
    the save here is the one the restore above will find."""
    save = _steps()[_at(_steps(), SAVE)]
    manifest = "hashFiles('pipeline/data/sources/planetiler_sources.json')"
    condition = " ".join(str(save["if"]).split())
    assert save["uses"].startswith("actions/cache/save@")
    assert "always()" in condition, "a fetch that failed part way must still save what arrived"
    assert "steps.planetiler_sources.outputs.fetched == 'true'" in condition, "save only when something was fetched"
    assert f"{manifest} != ''" in condition, "guard on the same file the key hashes"
    assert save["continue-on-error"] is True
    assert save["with"]["path"] == CACHED
    assert save["with"]["key"] == PREFIX + "${{ " + manifest + " }}"
