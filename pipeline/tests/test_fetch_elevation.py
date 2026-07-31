"""Tests for fetch_elevation.py - corridor-scoped USGS 3DEP 1m DEM tile
*discovery* (never download - see fetch_elevation.py's module docstring for
why nothing is downloaded here, unlike fetch_topo_quads.py).

Unlike fetch_topo_quads.py (a uniform nationwide quad grid with a
lightweight per-quad bbox CSV), 1m DEM tiles are organized as irregular
per-LiDAR-project S3 folders with no equivalent lightweight index - see
fetch_elevation.py's module docstring for why this uses the TNM Access API
(a real metadata layer over the same S3 bucket) for per-cell discovery
instead. These tests mock that API using a requests_mock fixture matched on
path only (no query-string matching) - the same pattern lib/arcgis.py's
pagination test uses, since the corridor grid cell varies per call but the
endpoint doesn't.

Also covered here: the corridor is built fresh from a centerline via
lib.corridor.build_corridor() rather than read from any fixed file (see
CENTERLINE_PATH), and write_gate_problems() - the count comparison that
gates main()'s final tile_index.json write. The latter is pure Python with
no network/DuckDB involved, unlike everything else in this file.
"""

import json

import pytest

import fetch_elevation
from fetch_elevation import compute_grid_cells, list_products_for_cell

# Same neighborhood/coordinates test_lib_corridor.py's, test_export_poi.py's,
# and test_export_trails.py's own synthetic centerline fixtures use (see
# test_spike_corridor.py) - far from any real data, so it can't collide with
# anything. Its 30-mile buffer spans just over 1 degree of longitude
# (verified empirically), so grid-chunking sees more than one cell.
CENTERLINE_COORDS = [(-74.0, 41.0), (-73.9, 41.1)]

# A short line near the equator, chosen only so its 30-mile buffer fits
# inside a single 1-degree grid cell (verified empirically - the buffer's
# EPSG:5070-projected extent shrinks approaching the equator, unlike a naive
# spherical estimate). Same "small enough to need only one grid cell"
# reasoning a fixed corridor rectangle fixture would use, just applied to a
# centerline that now needs buffering first.
SMALL_CENTERLINE_COORDS = [(-81.50, 20.00), (-81.49, 20.01)]


def _write_centerline(path, coords):
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
            }
        ],
    }
    path.write_text(json.dumps(fc))


# --- compute_grid_cells: grid-chunking + corridor freshness ---------------


def test_compute_grid_cells_returns_one_cell_for_a_small_corridor(tmp_path, monkeypatch):
    """A centerline short enough (and far enough from the poles) that its
    30-mile buffer fits inside a single 1x1-degree grid cell must produce
    exactly one cell - not zero (the corridor must not be lost entirely) and
    not spuriously more than one."""
    centerline_path = tmp_path / "centerline.geojson"
    _write_centerline(centerline_path, SMALL_CENTERLINE_COORDS)
    monkeypatch.setattr(fetch_elevation, "CENTERLINE_PATH", centerline_path)

    cells = compute_grid_cells()

    assert len(cells) == 1
    cx0, cy0, cx1, cy1 = cells[0]
    # The one cell actually covers the source line, not some unrelated area.
    assert cx0 < SMALL_CENTERLINE_COORDS[0][0] < cx1
    assert cy0 < SMALL_CENTERLINE_COORDS[0][1] < cy1


def test_compute_grid_cells_returns_multiple_cells_for_a_corridor_spanning_more_than_one_degree(tmp_path, monkeypatch):
    """A centerline whose 30-mile buffer spans more than one degree must be
    chunked into more than one grid cell, so each TNM Access API query stays
    small (see module docstring) rather than one giant query for the whole
    span."""
    centerline_path = tmp_path / "centerline.geojson"
    _write_centerline(centerline_path, CENTERLINE_COORDS)
    monkeypatch.setattr(fetch_elevation, "CENTERLINE_PATH", centerline_path)

    cells = compute_grid_cells()

    assert len(cells) > 1


def test_compute_grid_cells_builds_the_corridor_fresh_from_centerline_path_not_a_stale_file(tmp_path, monkeypatch):
    """Regression guard: this module used to read the confirmed-stale
    data/spike/corridor.geojson directly via a CORRIDOR_PATH constant (see
    lib/corridor.py's docstring for why that file must never be read). It
    must instead build the corridor fresh via lib.corridor.build_corridor()
    from CENTERLINE_PATH on every call - proven here by pointing
    CENTERLINE_PATH at two different centerlines in turn and confirming the
    grid cells actually differ, rather than coming from one fixed file
    regardless of input."""
    assert not hasattr(fetch_elevation, "CORRIDOR_PATH")

    small_path = tmp_path / "small.geojson"
    _write_centerline(small_path, SMALL_CENTERLINE_COORDS)
    monkeypatch.setattr(fetch_elevation, "CENTERLINE_PATH", small_path)
    small_cells = compute_grid_cells()

    wide_path = tmp_path / "wide.geojson"
    _write_centerline(wide_path, CENTERLINE_COORDS)
    monkeypatch.setattr(fetch_elevation, "CENTERLINE_PATH", wide_path)
    wide_cells = compute_grid_cells()

    assert len(small_cells) != len(wide_cells)


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


# --- write_gate_problems: the tile_index.json write gate (pure Python) ----


def test_write_gate_allows_a_first_run_at_or_above_the_cold_start_floor():
    assert fetch_elevation.write_gate_problems(None, fetch_elevation.COLD_START_MIN_TILES) == []


def test_write_gate_refuses_a_first_run_below_the_cold_start_floor():
    problems = fetch_elevation.write_gate_problems(None, fetch_elevation.COLD_START_MIN_TILES - 1)

    assert len(problems) == 1
    assert "cold-start floor" in problems[0]


def test_write_gate_allows_growth_over_the_previous_count():
    assert fetch_elevation.write_gate_problems(110, 244) == []


def test_write_gate_allows_a_shrink_within_tolerance():
    # 110 -> 95 is a ~13.6% drop, inside the default 15% tolerance.
    assert fetch_elevation.write_gate_problems(110, 95) == []


def test_write_gate_allows_a_shrink_exactly_at_the_tolerance_floor():
    # floor = 110 * (1 - 0.15) = 93.5, so 94 sits right at/above it.
    assert fetch_elevation.write_gate_problems(110, 94) == []


def test_write_gate_refuses_a_shrink_beyond_tolerance():
    # 110 -> 93 is a ~15.5% drop, just past the default 15% tolerance.
    problems = fetch_elevation.write_gate_problems(110, 93)

    assert len(problems) == 1
    assert "relative shrink check" in problems[0]
    assert "93" in problems[0]
    assert "110" in problems[0]


def test_write_gate_tolerance_self_scales_with_the_previous_count():
    """The relative check must scale with old_count rather than use a fixed
    tile-count threshold - a corridor that has grown far past today's real
    110 tiles must not need this tolerance retuned."""
    # 1000 -> 860 is a 14% drop (within tolerance); 1000 -> 840 is 16% (refused).
    assert fetch_elevation.write_gate_problems(1000, 860) == []
    assert fetch_elevation.write_gate_problems(1000, 840) != []


def test_write_gate_respects_a_custom_tolerance():
    assert fetch_elevation.write_gate_problems(100, 85, tolerance=0.10) != []  # 15% drop > 10% tolerance
    assert fetch_elevation.write_gate_problems(100, 85, tolerance=0.20) == []  # 15% drop < 20% tolerance


def test_write_gate_respects_a_custom_cold_start_minimum():
    assert fetch_elevation.write_gate_problems(None, 3, cold_start_min=2) == []
    assert fetch_elevation.write_gate_problems(None, 1, cold_start_min=2) != []


# --- _env_flag_set: the --allow-shrink override's env-var fallback --------


@pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "Yes"])
def test_env_flag_set_is_true_for_common_truthy_values(monkeypatch, value):
    monkeypatch.setenv(fetch_elevation.ALLOW_SHRINK_ENV_VAR, value)

    assert fetch_elevation._env_flag_set(fetch_elevation.ALLOW_SHRINK_ENV_VAR) is True


@pytest.mark.parametrize("value", ["0", "false", "False", ""])
def test_env_flag_set_is_false_for_falsy_values(monkeypatch, value):
    monkeypatch.setenv(fetch_elevation.ALLOW_SHRINK_ENV_VAR, value)

    assert fetch_elevation._env_flag_set(fetch_elevation.ALLOW_SHRINK_ENV_VAR) is False


def test_env_flag_set_is_false_when_unset(monkeypatch):
    monkeypatch.delenv(fetch_elevation.ALLOW_SHRINK_ENV_VAR, raising=False)

    assert fetch_elevation._env_flag_set(fetch_elevation.ALLOW_SHRINK_ENV_VAR) is False
