"""Regression test for the band-count mismatch bug in fix_corrupted_quads.py.

The bug as it actually happened: fetch_fallback() originally generated
substitute quads from a PNG32 (RGBA, 4-band) export, while the bulk USGS
quads are 3-band RGB. rasterio.merge.merge() requires matching band counts
across inputs - mixing them failed with "Dataset indexes and destination
buffer are mismatched", which only surfaced when spike_raster_mosaic.py
tried to merge a cell containing one of the substitutes, not at fixture-
generation time. The fix was dropping the alpha band before writing the
substitute (data = src.read((1, 2, 3)); profile update count=3).

This tests the underlying merge()-requires-matching-bands behavior directly
with tiny in-memory rasters, rather than calling fetch_fallback() itself
(which needs network + the metadata CSV) - the bug is in the band-count
contract between fetch_fallback()'s output and merge()'s input, not in any
particular network call.
"""

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.transform import from_bounds

import fix_corrupted_quads
from fix_corrupted_quads import fix_quad


def _make_raster(band_count: int, fill: int):
    """A tiny in-memory GeoTIFF-like dataset, same pattern as a real quad:
    uint8, EPSG:4326, small pixel grid."""
    transform = from_bounds(-74.1, 41.0, -74.0, 41.1, 10, 10)
    profile = {
        "driver": "GTiff",
        "height": 10,
        "width": 10,
        "count": band_count,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": transform,
    }
    memfile = MemoryFile()
    with memfile.open(**profile) as dataset:
        dataset.write(np.full((band_count, 10, 10), fill, dtype="uint8"))
    return memfile


def test_merging_mismatched_band_counts_fails():
    """Documents the actual failure: a 3-band bulk-style quad and a 4-band
    (RGBA) fallback-style quad can't be merged together directly."""
    bulk = _make_raster(3, fill=100)
    fallback_rgba = _make_raster(4, fill=200)

    with bulk.open() as bulk_ds, fallback_rgba.open() as fallback_ds:
        with pytest.raises(Exception):
            merge([bulk_ds, fallback_ds])

    bulk.close()
    fallback_rgba.close()


def test_dropping_alpha_band_before_merge_fixes_it():
    """The actual fix: normalize the fallback substitute to 3 bands (drop
    alpha) before merging - this is what fetch_fallback() does via
    `data = src.read((1, 2, 3))` + `profile.update(count=3)`."""
    bulk = _make_raster(3, fill=100)
    fallback_rgba = _make_raster(4, fill=200)

    # Reproduce fetch_fallback()'s normalization: read only bands 1-3, drop alpha.
    with fallback_rgba.open() as src:
        rgb_data = src.read((1, 2, 3))
        profile = src.profile
    profile.update(count=3)
    fallback_rgb = MemoryFile()
    with fallback_rgb.open(**profile) as dataset:
        dataset.write(rgb_data)

    with bulk.open() as bulk_ds, fallback_rgb.open() as fixed_ds:
        merged_arr, _ = merge([bulk_ds, fixed_ds])  # should not raise
        assert merged_arr.shape[0] == 3

    bulk.close()
    fallback_rgba.close()
    fallback_rgb.close()


def _write_geotiff_bytes(path, size=10, fill=100):
    transform = from_bounds(-74.1, 41.0, -74.0, 41.1, size, size)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((1, size, size), fill, dtype="uint8"))
    return path.read_bytes()


def _write_rgba_png_bytes(path, size=10, fill=150):
    """A valid 4-band (RGBA) PNG, matching what basemap.nationalmap.gov's
    export service actually returns (format=png32) - the real bug
    fetch_fallback() had to work around (see the two tests above)."""
    profile = {"driver": "PNG", "height": size, "width": size, "count": 4, "dtype": "uint8"}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((4, size, size), fill, dtype="uint8"))
    return path.read_bytes()


def test_fix_quad_returns_fixed_by_redownload_when_redownload_succeeds(tmp_path, requests_mock):
    """Redownload alone fixes it - the cheap, common path (fetch_corrupted_
    quads.py's own docstring: "not every quad has been double-checked this
    way," i.e. plenty of "corruption" is actually a bad first download)."""
    quad_path = tmp_path / "quads" / "CT" / "CT_Ansonia_20240815_TM_geo.tif"
    quad_path.parent.mkdir(parents=True)
    quad_path.write_bytes(b"corrupted junk currently on disk")

    valid_bytes = _write_geotiff_bytes(tmp_path / "source.tif")
    url = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/USTopo/GeoTIFF/CT/CT_Ansonia_20240815_TM_geo.tif"
    requests_mock.get(url, content=valid_bytes)

    # metadata_csv is never touched on this path (fetch_fallback only runs
    # if redownload fails) - a nonexistent path proves that.
    result = fix_quad("CT_Ansonia", quad_path, tmp_path / "nonexistent.csv", tmp_path / "fallback")

    assert result == {"status": "fixed_by_redownload"}
    assert quad_path.read_bytes() == valid_bytes


def test_fix_quad_falls_back_when_redownload_is_still_corrupted(tmp_path, requests_mock):
    quad_path = tmp_path / "quads" / "CT" / "CT_Ansonia_20240815_TM_geo.tif"
    quad_path.parent.mkdir(parents=True)
    quad_path.write_bytes(b"corrupted junk currently on disk")

    redownload_url = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/USTopo/GeoTIFF/CT/CT_Ansonia_20240815_TM_geo.tif"
    requests_mock.get(redownload_url, content=b"redownload did not help, still junk")

    metadata_csv = tmp_path / "ustopo_current.csv"
    metadata_csv.write_text("product_filename,westbc,eastbc,northbc,southbc\nCT_Ansonia.pdf,-73.125,-73.0,41.375,41.25\n")
    requests_mock.get(fix_corrupted_quads.EXPORT_URL, content=_write_rgba_png_bytes(tmp_path / "export.png"))

    fallback_dir = tmp_path / "fallback"
    result = fix_quad("CT_Ansonia", quad_path, metadata_csv, fallback_dir)

    assert result["status"] == "fallback"
    assert result["path"] == fallback_dir / "CT_Ansonia.tif"
    with rasterio.open(result["path"]) as src:
        assert src.count == 3  # alpha band dropped - the actual bug this script exists to fix


def test_fix_quad_reports_failed_when_both_redownload_and_fallback_fail(tmp_path, requests_mock):
    quad_path = tmp_path / "quads" / "CT" / "CT_Ansonia_20240815_TM_geo.tif"
    quad_path.parent.mkdir(parents=True)
    quad_path.write_bytes(b"corrupted junk currently on disk")

    redownload_url = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/USTopo/GeoTIFF/CT/CT_Ansonia_20240815_TM_geo.tif"
    requests_mock.get(redownload_url, content=b"still junk")

    metadata_csv = tmp_path / "ustopo_current.csv"
    metadata_csv.write_text("product_filename,westbc,eastbc,northbc,southbc\nCT_Ansonia.pdf,-73.125,-73.0,41.375,41.25\n")
    requests_mock.get(fix_corrupted_quads.EXPORT_URL, content=b"not a real image either")

    result = fix_quad("CT_Ansonia", quad_path, metadata_csv, tmp_path / "fallback")

    assert result == {"status": "failed"}
