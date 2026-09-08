"""Tests for lib/manifest_paths.py - the fix for #1265: a manifest path has
to name the same file whether it is read by the job that wrote it or by a
different one, which absolute paths only did by accident of both jobs
checking out the repo to the same workspace path.
"""

from pathlib import Path

from lib.manifest_paths import PIPELINE_ROOT, from_manifest_path, to_manifest_path


def test_round_trips_a_real_pipeline_path():
    original = PIPELINE_ROOT / "data" / "processed" / "trails.geojson"

    relative = to_manifest_path(original)

    assert relative == "data/processed/trails.geojson"
    assert from_manifest_path(relative) == original


def test_is_relative_regardless_of_which_job_wrote_it():
    """The whole point: two processes with different absolute checkouts
    (different jobs, different runners) resolve the same manifest entry to
    their own pipeline/, not to wherever the writer happened to run."""
    relative = to_manifest_path(PIPELINE_ROOT / "data" / "raw" / "atc_updates.json")

    other_root = Path("/some/other/runners/workspace/OurHike/pipeline")
    assert other_root / relative == other_root / "data" / "raw" / "atc_updates.json"


def test_falls_back_to_absolute_outside_the_pipeline_directory():
    """Every exporter's output is under PIPELINE_ROOT in practice, but a
    path that is not (a test fixture's tmp_path, say) still has to publish
    something rather than crash the export - the same fallback
    lib/fetch_receipts.py's recorded_path already uses."""
    outside = "/tmp/somewhere/else/trails.geojson"

    assert to_manifest_path(outside) == outside


def test_an_absolute_manifest_path_passes_through_unchanged():
    """Not every caller of publish() goes through an exporter's manifest -
    test fixtures build an artifacts dict by hand with an absolute tmp_path.
    Those have to keep working unchanged rather than being reinterpreted as
    relative to pipeline/."""
    absolute = "/tmp/pytest-of-runner/test_xyz0/artifact.geojson"

    assert from_manifest_path(absolute) == Path(absolute)
