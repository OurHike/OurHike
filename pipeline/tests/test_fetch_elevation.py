"""HTTP-mocked tests for fetch_elevation.py - corridor-scoped USGS 3DEP 1m
DEM tile discovery/download.

Unlike fetch_topo_quads.py (a uniform nationwide quad grid with a
lightweight per-quad bbox CSV), 1m DEM tiles are organized as irregular
per-LiDAR-project S3 folders with no equivalent lightweight index - see
fetch_elevation.py's module docstring for why this uses the TNM Access API
(a real metadata layer over the same S3 bucket) for per-cell discovery
instead. These tests mock that API alongside the same S3 HEAD/GET +
rasterio-readability flow fetch_topo_quads.py already established, using a
requests_mock fixture matched on path only (no query-string matching) - the
same pattern lib/arcgis.py's pagination test uses, since the corridor grid
cell varies per call but the endpoint doesn't.
"""

import json

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

import fetch_elevation
from fetch_elevation import compute_grid_cells, list_products_for_cell

# A small square fixture corridor - fits inside exactly one 1-degree grid
# cell, so tests only need to mock one TNM Access API call.
CORRIDOR_BOUNDS = (-75.05, 41.0, -74.95, 41.1)  # west, south, east, north

INSIDE_URL = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/VA_Fake_2020/TIFF/USGS_1M_17_x54y410_VA_Fake_2020.tif"
)
OUTSIDE_URL = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/VA_Fake_2020/TIFF/USGS_1M_17_x99y999_VA_Fake_2020.tif"
)


def _write_corridor(path, bounds):
    west, south, east, north = bounds
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
                },
            }
        ],
    }
    path.write_text(json.dumps(fc))


def _write_triangle_corridor(path):
    """A non-rectangular corridor: the base spans CORRIDOR_BOUNDS' full
    width, but the shape narrows to a point at the north edge - used to
    prove tile-vs-corridor filtering checks the real polygon, not just the
    corridor's bounding rectangle (which a plain rectangle fixture can't
    distinguish, since bbox-vs-corridor and bbox-vs-cell would always agree)."""
    west, south, east, north = CORRIDOR_BOUNDS
    apex_x = (west + east) / 2
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[west, south], [east, south], [apex_x, north], [west, south]]],
                },
            }
        ],
    }
    path.write_text(json.dumps(fc))


def _tif_bytes(bounds, size=10):
    """A tiny valid single-band GeoTIFF, as real bytes - used as the
    requests_mock response body for a "download" so the code under test
    writes real, rasterio-readable content to disk."""
    transform = from_bounds(*bounds, size, size)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
    }
    with MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            dataset.write(np.full((1, size, size), 500.0, dtype="float32"))
        return bytes(memfile.read())


def _corrupted_tif_bytes(tmp_path, bounds, height=200, width=50):
    """A real multi-strip LZW-compressed TIFF truncated to 70% of its length
    - same technique test_spike_raster_mosaic.py uses to reproduce the real
    corruption mode found in 3 of 1,654 topo quads: the header and first
    strip(s) stay intact, later strips don't, so a corner-pixel read would
    miss it but a full-band read won't."""
    full_path = tmp_path / "_full_for_corruption.tif"
    transform = from_bounds(*bounds, width, height)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": transform,
        "compress": "lzw",
        "blockysize": 16,
        "tiled": False,
    }
    with rasterio.open(full_path, "w", **profile) as dst:
        dst.write(np.random.randint(1, 255, (1, height, width), dtype="uint8"))
    data = full_path.read_bytes()
    return data[: int(len(data) * 0.7)]


def _setup(tmp_path, monkeypatch, write_corridor=None):
    corridor_path = tmp_path / "corridor.geojson"
    (write_corridor or (lambda p: _write_corridor(p, CORRIDOR_BOUNDS)))(corridor_path)
    out_dir = tmp_path / "data" / "raw" / "elevation"
    manifest_path = out_dir / "manifest.json"
    # ROOT is monkeypatched too (not just OUT_DIR) since main() records each
    # downloaded tile's path in the manifest relative to ROOT - without this,
    # that relative_to() call fails outright because tmp_path isn't really
    # under the pipeline's real ROOT.
    monkeypatch.setattr(fetch_elevation, "ROOT", tmp_path)
    monkeypatch.setattr(fetch_elevation, "CORRIDOR_PATH", corridor_path)
    monkeypatch.setattr(fetch_elevation, "OUT_DIR", out_dir)
    monkeypatch.setattr(fetch_elevation, "MANIFEST_PATH", manifest_path)
    return out_dir, manifest_path


def _mock_tnm_response(requests_mock, items):
    requests_mock.get(fetch_elevation.TNM_API_URL, json={"total": len(items), "items": items})


# --- parse_tile_url ---------------------------------------------------


def test_compute_grid_cells_returns_one_cell_for_a_small_corridor(tmp_path, monkeypatch):
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, CORRIDOR_BOUNDS)
    monkeypatch.setattr(fetch_elevation, "CORRIDOR_PATH", corridor_path)

    cells = compute_grid_cells()

    assert len(cells) == 1
    cx0, cy0, cx1, cy1 = cells[0]
    assert cx0 == pytest.approx(CORRIDOR_BOUNDS[0])
    assert cy0 == pytest.approx(CORRIDOR_BOUNDS[1])


def test_compute_grid_cells_returns_multiple_cells_for_a_corridor_spanning_more_than_one_degree(tmp_path, monkeypatch):
    corridor_path = tmp_path / "corridor.geojson"
    _write_corridor(corridor_path, (-76.0, 40.0, -74.0, 41.5))  # 2deg wide, 1.5deg tall
    monkeypatch.setattr(fetch_elevation, "CORRIDOR_PATH", corridor_path)

    cells = compute_grid_cells()

    assert len(cells) > 1


# --- list_products_for_cell ---------------------------------------------


def test_list_products_for_cell_paginates_when_total_exceeds_one_page(requests_mock):
    """The TNM Access API caps items per response - a cell dense enough to
    exceed that cap must page via offset until every item's been collected,
    not silently return a truncated first page."""
    page1 = {"total": 3, "items": [{"downloadURL": "u1"}, {"downloadURL": "u2"}]}
    page2 = {"total": 3, "items": [{"downloadURL": "u3"}]}
    requests_mock.get(fetch_elevation.TNM_API_URL, [{"json": page1}, {"json": page2}])

    items = list_products_for_cell((-75.0, 41.0, -74.0, 42.0))

    assert [item["downloadURL"] for item in items] == ["u1", "u2", "u3"]


def test_list_products_for_cell_stops_after_a_single_page_when_total_fits(requests_mock):
    page = {"total": 2, "items": [{"downloadURL": "u1"}, {"downloadURL": "u2"}]}
    requests_mock.get(fetch_elevation.TNM_API_URL, [{"json": page}])  # only one response registered

    items = list_products_for_cell((-75.0, 41.0, -74.0, 42.0))  # should not raise NoMockAddress from a second call

    assert [item["downloadURL"] for item in items] == ["u1", "u2"]


# --- main(): skip / download / corridor-filter / validate ---------------
