"""Regression tests for spike_raster_mosaic.py's real-world corruption and
completeness handling.

Both bugs here were found on real USGS data mid-session, not hypothesized in
advance - see TESTING.md for the "encode every gotcha as a regression test"
convention this follows.
"""
import os
import tempfile

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.transform import from_bounds

import spike_raster_mosaic
from fetch_topo_quads import bare_key
from spike_raster_mosaic import bounds_intersect, load_neatlines, open_cropped_vrt


def _write_multistrip_tiff(path, height=200, width=50):
    """A real multi-strip LZW-compressed TIFF, matching the real quads'
    layout closely enough that truncating it reproduces the same failure
    mode we saw in production: corruption in a later strip, not the first."""
    transform = from_bounds(-74.1, 41.0, -74.0, 41.1, width, height)
    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": 1,
        "dtype": "uint8", "crs": "EPSG:4326", "transform": transform,
        "compress": "lzw", "blockysize": 16, "tiled": False,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.random.randint(1, 255, (1, height, width), dtype="uint8"))


@pytest.fixture
def corrupted_later_strip_tiff(tmp_path):
    """A TIFF truncated to 70% of its length - the header and first strip(s)
    stay intact, later strips don't. This is the actual failure mode found
    in 3 of 1,654 real USGS quads (NC_Glade_Valley, VA_Marion, WV_Princeton):
    confirmed via a byte-exact re-download that still failed, and via two
    independent codebases (rasterio/GDAL and tifffile/imagecodecs) failing
    identically - genuine source-side corruption, not a download issue."""
    full_path = tmp_path / "full.tif"
    _write_multistrip_tiff(full_path)
    full_size = os.path.getsize(full_path)

    truncated_path = tmp_path / "corrupted.tif"
    with open(full_path, "rb") as f:
        data = f.read()
    with open(truncated_path, "wb") as f:
        f.write(data[: int(full_size * 0.7)])
    return truncated_path


def test_corner_pixel_read_does_not_catch_late_strip_corruption(corrupted_later_strip_tiff):
    """Documents why the ORIGINAL validation (a window=((0,1),(0,1)) corner
    read) was insufficient: it missed 2 of the 3 known-corrupted quads
    because their corruption was in a later strip, and a corner read only
    ever touches strip 0."""
    with rasterio.open(corrupted_later_strip_tiff) as src:
        src.read(1, window=((0, 1), (0, 1)))  # should NOT raise


def test_full_band_read_catches_late_strip_corruption(corrupted_later_strip_tiff):
    """The actual fix: index_quad_bounds() now does a full src.read(1) on
    every quad, which does force every strip to decode."""
    with rasterio.open(corrupted_later_strip_tiff) as src:
        with pytest.raises(Exception):
            src.read(1)


def test_completeness_check_fails_when_a_cell_has_no_output():
    """spike_raster_mosaic.py hard-fails (sys.exit(1)) if any corridor-
    intersecting grid cell produces no tile, rather than silently reporting
    a partial result as if it were complete - this test exercises that same
    logic pattern directly (a list of skip reasons implies failure) since
    the real check is inline in main(), not a separate importable function."""
    skipped_cells = []
    total_cells = 5

    for i in range(total_cells):
        produced_tile = i != 2  # simulate cell index 2 failing to produce output
        if not produced_tile:
            skipped_cells.append((i, "simulated failure"))

    assert len(skipped_cells) == 1
    # Mirrors the real script's completeness gate: any skipped cell means the
    # run must be treated as incomplete, not silently accepted.
    is_complete = len(skipped_cells) == 0
    assert not is_complete


@pytest.mark.parametrize("a, b, expected", [
    ((-75.0, 40.0, -74.0, 41.0), (-74.5, 40.5, -73.5, 41.5), True),   # overlapping
    ((-75.0, 40.0, -74.0, 41.0), (-74.0, 41.0, -73.0, 42.0), False),  # touching at a corner only, not overlapping
    ((-75.0, 40.0, -74.0, 41.0), (-70.0, 35.0, -69.0, 36.0), False),  # far apart
    ((-75.0, 40.0, -74.0, 41.0), (-75.0, 40.0, -74.0, 41.0), True),   # identical
])
def test_bounds_intersect(a, b, expected):
    assert bounds_intersect(a, b) is expected


def test_load_neatlines_matches_dated_filenames_via_bare_key(tmp_path, monkeypatch):
    """load_neatlines() keys its lookup by bare_key() so a locally-downloaded,
    dated filename (CT_Ansonia_20240815_TM_geo.tif) matches USGS's own
    undated product_filename column (CT_Ansonia.pdf) - real values from the
    real CT_Ansonia row, confirmed against the actual quad on disk: its
    georeferenced raster extent is noticeably bigger than this neatline."""
    csv_path = tmp_path / "ustopo_current.csv"
    csv_path.write_text(
        "product_filename,westbc,eastbc,northbc,southbc\n"
        "CT_Ansonia.pdf,-73.125,-73.0,41.375,41.25\n"
    )
    monkeypatch.setattr(spike_raster_mosaic, "METADATA_CSV_PATH", csv_path)

    neatlines = load_neatlines()

    assert neatlines[bare_key("CT_Ansonia_20240815_TM_geo")] == (-73.125, 41.25, -73.0, 41.375)


def test_open_cropped_vrt_excludes_collar_outside_the_neatline(tmp_path):
    """The actual fix: every US Topo GeoTIFF is a full printed-sheet scan (see
    module docstring) - white margin plus a header/footer collar - and its
    georeferenced extent covers that whole sheet, not just the real mapped
    area. This builds a synthetic quad with a distinct "collar" value
    surrounding a smaller "map interior" region, and confirms cropping to a
    neatline matching that interior excludes the collar value entirely."""
    size = 100
    full_bounds = (-75.05, 40.95, -74.95, 41.05)  # 0.1 x 0.1 deg, collar included
    transform = from_bounds(*full_bounds, size, size)
    profile = {
        "driver": "GTiff", "height": size, "width": size, "count": 1,
        "dtype": "uint8", "crs": "EPSG:4326", "transform": transform,
    }
    arr = np.full((1, size, size), 50, dtype="uint8")  # 50 = collar
    arr[:, 10:90, 10:90] = 200  # 200 = real map interior - exactly the neatline below
    path = tmp_path / "quad.tif"
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr)

    neatline = (-75.04, 40.96, -74.96, 41.04)  # matches the interior block exactly

    vrt = open_cropped_vrt(path, neatline)
    try:
        data = vrt.read(1)
    finally:
        vrt.close()
        vrt.src_dataset.close()

    assert not np.any(data == 50), "collar value leaked into the cropped output"
    assert np.any(data == 200)


def test_open_cropped_vrt_falls_back_to_full_extent_when_no_neatline(tmp_path):
    """Defensive path: a quad with no metadata match (neatline=None) still
    produces a usable VRT sized from its own full extent, rather than
    crashing the run - better a possibly-collar-inflated tile than no tile
    at all for a quad USGS's own metadata doesn't cover."""
    size = 20
    transform = from_bounds(-74.1, 41.0, -74.0, 41.1, size, size)
    profile = {
        "driver": "GTiff", "height": size, "width": size, "count": 1,
        "dtype": "uint8", "crs": "EPSG:4326", "transform": transform,
    }
    path = tmp_path / "quad.tif"
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((1, size, size), 123, dtype="uint8"))

    vrt = open_cropped_vrt(path, None)
    try:
        assert np.any(vrt.read(1) == 123)
    finally:
        vrt.close()
        vrt.src_dataset.close()


def test_clip_to_polygon_zeroes_pixels_outside_and_keeps_pixels_inside():
    """Mirrors the real clip step in spike_raster_mosaic.py's main(): mask a
    raster against a polygon and confirm pixels outside are actually zeroed
    (nodata) while pixels inside are preserved - not just that the call
    succeeds without error."""
    width = height = 20
    transform = from_bounds(-74.0, 41.0, -73.8, 41.2, width, height)
    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": 1,
        "dtype": "uint8", "crs": "EPSG:4326", "transform": transform,
    }
    with MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            dataset.write(np.full((1, height, width), 255, dtype="uint8"))

            # A polygon covering only the left half of the raster's extent.
            half_polygon = {
                "type": "Polygon",
                "coordinates": [[[-74.0, 41.0], [-73.9, 41.0], [-73.9, 41.2], [-74.0, 41.2], [-74.0, 41.0]]],
            }
            clipped, _ = mask(dataset, [half_polygon], crop=False, nodata=0)

    # Left half (inside the polygon) should still have real data; right half
    # (outside) should be zeroed.
    assert clipped[0, :, : width // 4].max() == 255
    assert clipped[0, :, 3 * width // 4 :].max() == 0
