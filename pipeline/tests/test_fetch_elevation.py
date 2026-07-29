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
from fetch_elevation import compute_grid_cells, list_products_for_cell, parse_tile_url

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


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/"
            "VA_FEMA-NRCS_SouthCentral_2017_D17/TIFF/USGS_1M_17_x54y410_VA_FEMA-NRCS_SouthCentral_2017_D17.tif",
            ("VA", "VA_FEMA-NRCS_SouthCentral_2017_D17", "USGS_1M_17_x54y410_VA_FEMA-NRCS_SouthCentral_2017_D17.tif"),
        ),
        (
            # Real, observed inconsistency: some projects/vintages use lowercase
            # "1m" with no UTM-zone digit before the grid cell ID.
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/"
            "AL_25Co_B1_2017/TIFF/USGS_1m_x51y383_AL_25Co_B1_2017.tif",
            ("AL", "AL_25Co_B1_2017", "USGS_1m_x51y383_AL_25Co_B1_2017.tif"),
        ),
    ],
)
def test_parse_tile_url(url, expected):
    assert parse_tile_url(url) == expected


def test_parse_tile_url_raises_on_unexpected_url_shape():
    """Defensive: a URL that doesn't match the real .../Projects/<x>/TIFF/<y>
    shape should fail loudly, not silently return garbage a caller might use
    to build a bad local path."""
    with pytest.raises(ValueError):
        parse_tile_url("https://example.com/not/a/real/tile/path.tif")


# --- compute_grid_cells -------------------------------------------------


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


def test_fetch_elevation_skips_a_tile_whose_last_modified_is_unchanged_from_the_manifest(tmp_path, monkeypatch, requests_mock):
    out_dir, manifest_path = _setup(tmp_path, monkeypatch)
    local_path = out_dir / "VA" / "USGS_1M_17_x54y410_VA_Fake_2020.tif"
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(_tif_bytes(CORRIDOR_BOUNDS))
    manifest_path.write_text(
        json.dumps({INSIDE_URL: {"last_modified": "Wed, 01 Jan 2025 00:00:00 GMT", "local_path": str(local_path)}})
    )

    inside_bbox = {"minX": CORRIDOR_BOUNDS[0], "minY": CORRIDOR_BOUNDS[1], "maxX": CORRIDOR_BOUNDS[2], "maxY": CORRIDOR_BOUNDS[3]}
    _mock_tnm_response(requests_mock, [{"downloadURL": INSIDE_URL, "boundingBox": inside_bbox}])
    requests_mock.head(INSIDE_URL, headers={"Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"})
    # Deliberately no GET mock for INSIDE_URL - if the skip logic fails and
    # main() tries to re-download anyway, requests_mock raises NoMockAddress
    # and this test fails loudly, exactly the isolation guarantee wanted
    # (same pattern as test_fetch_all.py's unchanged-source test).

    fetch_elevation.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest[INSIDE_URL]["last_modified"] == "Wed, 01 Jan 2025 00:00:00 GMT"


def test_fetch_elevation_downloads_a_tile_intersecting_the_corridor(tmp_path, monkeypatch, requests_mock):
    out_dir, manifest_path = _setup(tmp_path, monkeypatch)

    inside_bbox = {"minX": CORRIDOR_BOUNDS[0], "minY": CORRIDOR_BOUNDS[1], "maxX": CORRIDOR_BOUNDS[2], "maxY": CORRIDOR_BOUNDS[3]}
    _mock_tnm_response(requests_mock, [{"downloadURL": INSIDE_URL, "boundingBox": inside_bbox}])
    requests_mock.head(INSIDE_URL, headers={"Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"})
    requests_mock.get(INSIDE_URL, content=_tif_bytes(CORRIDOR_BOUNDS))

    fetch_elevation.main()

    local_path = out_dir / "VA" / "USGS_1M_17_x54y410_VA_Fake_2020.tif"
    assert local_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest[INSIDE_URL]["last_modified"] == "Wed, 01 Jan 2025 00:00:00 GMT"
    assert manifest[INSIDE_URL]["local_path"] == str(local_path.relative_to(fetch_elevation.ROOT))


def test_fetch_elevation_does_not_download_a_tile_outside_the_corridor(tmp_path, monkeypatch, requests_mock):
    out_dir, _ = _setup(tmp_path, monkeypatch, write_corridor=_write_triangle_corridor)

    # Near the triangle's base - well inside the real polygon.
    inside_bbox = {"minX": -75.01, "minY": 41.0, "maxX": -74.99, "maxY": 41.02}
    # In the corner of the corridor's own *bounding rectangle* the triangle
    # never actually reaches - a bbox-vs-cell check alone would wrongly
    # accept this; only a bbox-vs-real-polygon check correctly excludes it.
    outside_bbox = {"minX": -75.05, "minY": 41.08, "maxX": -75.03, "maxY": 41.1}
    _mock_tnm_response(
        requests_mock,
        [
            {"downloadURL": INSIDE_URL, "boundingBox": inside_bbox},
            {"downloadURL": OUTSIDE_URL, "boundingBox": outside_bbox},
        ],
    )
    requests_mock.head(INSIDE_URL, headers={"Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"})
    requests_mock.get(INSIDE_URL, content=_tif_bytes((-75.01, 41.0, -74.99, 41.02)))
    # Deliberately no HEAD/GET mock for OUTSIDE_URL - if the corridor filter
    # fails and main() tries to fetch it anyway, requests_mock raises
    # NoMockAddress and this test fails loudly.

    fetch_elevation.main()

    assert (out_dir / "VA" / "USGS_1M_17_x54y410_VA_Fake_2020.tif").exists()
    assert not (out_dir / "VA" / "USGS_1M_17_x99y999_VA_Fake_2020.tif").exists()


def test_fetch_elevation_validates_downloaded_tile_readability_not_just_http_status(tmp_path, monkeypatch, requests_mock):
    """Mirrors fetch_topo_quads.py's real-corruption-catching discipline: a
    tile can download with HTTP 200 and a plausible Content-Length yet still
    be genuinely unreadable - that must be caught and excluded from the
    manifest, not trusted just because the HTTP layer reported success."""
    out_dir, manifest_path = _setup(tmp_path, monkeypatch)

    inside_bbox = {"minX": CORRIDOR_BOUNDS[0], "minY": CORRIDOR_BOUNDS[1], "maxX": CORRIDOR_BOUNDS[2], "maxY": CORRIDOR_BOUNDS[3]}
    _mock_tnm_response(requests_mock, [{"downloadURL": INSIDE_URL, "boundingBox": inside_bbox}])
    requests_mock.head(INSIDE_URL, headers={"Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"})
    requests_mock.get(INSIDE_URL, content=_corrupted_tif_bytes(tmp_path, CORRIDOR_BOUNDS), status_code=200)

    fetch_elevation.main()  # should not raise despite the corrupted download

    manifest = json.loads(manifest_path.read_text())
    assert INSIDE_URL not in manifest, "a corrupted tile must not be recorded as successfully fetched"
    local_path = out_dir / "VA" / "USGS_1M_17_x54y410_VA_Fake_2020.tif"
    with pytest.raises(Exception):
        with rasterio.open(local_path) as src:
            src.read(1)  # confirms the fixture really is unreadable, not a vacuous pass
