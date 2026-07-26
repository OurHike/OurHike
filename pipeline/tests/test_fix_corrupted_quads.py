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
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.transform import from_bounds


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
