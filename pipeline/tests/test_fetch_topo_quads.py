import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

import fetch_topo_quads
from fetch_topo_quads import BUCKET_URL, GEOTIFF_PREFIX, bare_key, completeness_problems, fetch_one_quad, fetch_quads_for_cell


@pytest.mark.parametrize(
    "filename_no_ext, expected",
    [
        ("AL_Abbeville_East_20240208_TM_geo", "AL_Abbeville_East"),
        ("NC_Glade_Valley_20220908_TM_geo", "NC_Glade_Valley"),
        ("CT_Ansonia", "CT_Ansonia"),  # no date suffix - the inconsistency that caused the original bug
        ("WV_Princeton_20230615_TM_geo", "WV_Princeton"),
    ],
)
def test_bare_key(filename_no_ext, expected):
    assert bare_key(filename_no_ext) == expected


def test_bare_key_lets_dated_and_undated_forms_match():
    """The actual bug: some CSV rows have the dated filename, others the
    plain form, for the same physical quad - bare_key() must normalize both
    to the same key so they match against the real S3 filename listing."""
    assert bare_key("VA_Marion_20220916_TM_geo") == bare_key("VA_Marion")


def _write_tiny_geotiff(path):
    transform = from_bounds(-74.1, 41.0, -74.0, 41.1, 4, 4)
    profile = {
        "driver": "GTiff",
        "height": 4,
        "width": 4,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((1, 4, 4), 100, dtype="uint8"))
    return path.read_bytes()


STATE_INDEX = {"CT": {"CT_Ansonia": "CT_Ansonia_20240815_TM_geo.tif"}}
TIF_URL = f"{BUCKET_URL}/{GEOTIFF_PREFIX}/CT/CT_Ansonia_20240815_TM_geo.tif"


def test_fetch_one_quad_downloads_a_new_quad_and_updates_the_manifest(tmp_path, requests_mock):
    valid_bytes = _write_tiny_geotiff(tmp_path / "source.tif")
    requests_mock.head(TIF_URL, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    requests_mock.get(TIF_URL, content=valid_bytes)
    manifest = {}

    result = fetch_one_quad("CT_Ansonia.pdf", STATE_INDEX, tmp_path / "out", manifest)

    assert result["status"] == "downloaded"
    assert result["bytes"] == len(valid_bytes)
    assert (tmp_path / "out" / "CT" / "CT_Ansonia_20240815_TM_geo.tif").exists()
    assert manifest[TIF_URL]["last_modified"] == "Tue, 01 Jul 2025 00:00:00 GMT"


def test_fetch_one_quad_skips_when_manifest_matches_and_file_exists(tmp_path, requests_mock):
    out_dir = tmp_path / "out"
    local_path = out_dir / "CT" / "CT_Ansonia_20240815_TM_geo.tif"
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(b"already here")
    requests_mock.head(TIF_URL, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    manifest = {TIF_URL: {"last_modified": "Tue, 01 Jul 2025 00:00:00 GMT", "local_path": "irrelevant"}}

    result = fetch_one_quad("CT_Ansonia.pdf", STATE_INDEX, out_dir, manifest)

    assert result["status"] == "skipped"
    assert requests_mock.call_count == 1  # HEAD only, no GET - the file wasn't re-downloaded


def test_fetch_one_quad_refetches_when_remote_last_modified_header_is_missing(tmp_path, requests_mock):
    """A missing remote Last-Modified header must never be treated as
    "matches the manifest" just because both sides then compare equal as
    None - that would silently skip a re-fetch forever for a quad whose
    manifest entry has no recorded last_modified, even though the local file
    is already present."""
    out_dir = tmp_path / "out"
    local_path = out_dir / "CT" / "CT_Ansonia_20240815_TM_geo.tif"
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(b"stale copy")
    requests_mock.head(TIF_URL)  # no Last-Modified header in the response
    valid_bytes = _write_tiny_geotiff(tmp_path / "source.tif")
    requests_mock.get(TIF_URL, content=valid_bytes)
    manifest = {TIF_URL: {"local_path": "irrelevant"}}  # no last_modified recorded

    result = fetch_one_quad("CT_Ansonia.pdf", STATE_INDEX, out_dir, manifest)

    assert result["status"] == "downloaded"
    assert requests_mock.call_count == 2  # HEAD *and* GET - it actually re-fetched rather than skipping


def test_fetch_one_quad_reports_unmatched_when_no_geotiff_found(tmp_path):
    result = fetch_one_quad("VT_Somewhere.pdf", STATE_INDEX, tmp_path / "out", {})

    assert result["status"] == "unmatched"
    assert result["reason"] == "no_match"


def test_fetch_one_quad_reports_unmatched_when_head_fails(tmp_path, requests_mock):
    requests_mock.head(TIF_URL, status_code=404)

    result = fetch_one_quad("CT_Ansonia.pdf", STATE_INDEX, tmp_path / "out", {})

    assert result["status"] == "unmatched"
    assert result["reason"] == "head_failed"


def test_fetch_one_quad_reports_corrupted_when_downloaded_file_fails_to_read(tmp_path, requests_mock):
    garbage = b"not a real geotiff"
    requests_mock.head(TIF_URL, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    requests_mock.get(TIF_URL, content=garbage)
    manifest = {}

    result = fetch_one_quad("CT_Ansonia.pdf", STATE_INDEX, tmp_path / "out", manifest)

    assert result["status"] == "corrupted"
    assert TIF_URL not in manifest  # a corrupted download must not be recorded as a good fetch
    # A corrupted download still transferred real bytes over the network -
    # main()'s summary line should keep counting them, matching what the
    # pre-refactor code did (it added to total_bytes before the corruption
    # check ran at all).
    assert result["bytes"] == len(garbage)


def test_fetch_one_quad_stores_manifest_local_path_relative_to_root_when_possible(tmp_path, requests_mock):
    """local_path in the manifest is write-only bookkeeping (never read back
    - see fetch_topo_quads.py's comment), but should still reproduce the
    original relative-to-ROOT format whenever out_dir is under ROOT, falling
    back to absolute only when it isn't (e.g. this test's tmp_path)."""
    valid_bytes = _write_tiny_geotiff(tmp_path / "source.tif")
    requests_mock.head(TIF_URL, headers={"Last-Modified": "Tue, 01 Jul 2025 00:00:00 GMT"})
    requests_mock.get(TIF_URL, content=valid_bytes)
    manifest = {}

    fetch_one_quad("CT_Ansonia.pdf", STATE_INDEX, tmp_path / "out", manifest)

    # tmp_path isn't under ROOT, so this must fall back to an absolute path
    # rather than raising - and it must still be the real file's path.
    stored = Path(manifest[TIF_URL]["local_path"])
    assert stored.is_absolute()
    assert stored == tmp_path / "out" / "CT" / "CT_Ansonia_20240815_TM_geo.tif"


def test_fetch_quads_for_cell_returns_one_result_per_quad_in_order(tmp_path, requests_mock):
    requests_mock.head(TIF_URL, status_code=404)  # only quad in STATE_INDEX; everything else unmatched

    results = fetch_quads_for_cell(["CT_Ansonia.pdf", "VT_Ghost.pdf"], STATE_INDEX, tmp_path / "out", {})

    assert len(results) == 2
    assert results[0]["status"] == "unmatched"  # CT_Ansonia: HEAD 404
    assert results[1]["status"] == "unmatched"  # VT_Ghost: no state entry at all


def test_fetch_metadata_csv_refetches_when_remote_last_modified_header_is_missing(tmp_path, monkeypatch, requests_mock):
    """Same None == None trap as fetch_one_quad(), one level up: a
    fetch_state.json with no recorded last_modified plus a remote response
    with no Last-Modified header must not be treated as "unchanged", even
    though a (here, stale) CSV already exists on disk."""
    metadata_dir = tmp_path / "topo_metadata"
    metadata_dir.mkdir()
    csv_path = metadata_dir / "ustopo_current.csv"
    csv_path.write_text("stale content")
    state_path = metadata_dir / "fetch_state.json"
    state_path.write_text(json.dumps({}))  # no last_modified recorded
    monkeypatch.setattr(fetch_topo_quads, "METADATA_DIR", metadata_dir)
    monkeypatch.setattr(fetch_topo_quads, "METADATA_STATE_PATH", state_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ustopo_current.csv", "fresh content")
    requests_mock.head(fetch_topo_quads.METADATA_URL)  # no Last-Modified header
    requests_mock.get(fetch_topo_quads.METADATA_URL, content=buf.getvalue())

    result = fetch_topo_quads.fetch_metadata_csv()

    assert result == csv_path
    assert csv_path.read_text() == "fresh content"  # it actually re-fetched rather than skipping


def test_completeness_problems_is_empty_when_nothing_corrupted_or_unmatched():
    assert completeness_problems(unmatched=0, corrupted=0) == []


def test_completeness_problems_flags_any_corrupted_quad_as_fatal():
    """A corrupted quad is always our own data-quality problem (we matched
    and downloaded it fine; the bytes just don't decode - see
    fetch_one_quad()'s post-download validation), so it must always gate the
    run's exit code, regardless of the unmatched count."""
    problems = completeness_problems(unmatched=0, corrupted=2)

    assert len(problems) == 1
    assert "2" in problems[0]


def test_completeness_problems_does_not_gate_on_unmatched_quads_alone():
    """Deliberate judgment call (see completeness_problems()'s docstring): an
    unmatched quad can reflect a genuine gap in USGS's own metadata
    inventory rather than a defect in this script's matching logic, so a
    large unmatched count alone must not fail the run."""
    assert completeness_problems(unmatched=50, corrupted=0) == []


def test_completeness_problems_still_gates_on_corrupted_alongside_unmatched():
    """Unmatched quads don't suppress the corrupted gate - the two counts are
    judged independently."""
    problems = completeness_problems(unmatched=50, corrupted=1)

    assert len(problems) == 1
