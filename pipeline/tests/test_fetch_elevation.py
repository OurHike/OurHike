"""Tests for fetch_elevation.py - the corridor's 3DEP tile index.

Never a download: see fetch_elevation.py's module docstring for why nothing is
fetched here, unlike fetch_topo_quads.py.

**These tests make no network calls at all, and that is the change they are
testing.** This file used to mock the TNM Access API, because the tile list was
discovered by asking it once per corridor cell. 3DEP's 1/3 arc-second product
is a uniform 1-degree grid with a deterministic URL per cell, so the list is now
arithmetic over the corridor's bounding box (#550, ELEVATION_SOURCES.md section
3). A test that needs a mocked HTTP endpoint to find out which tiles cover
Georgia would be testing a design that no longer exists.

Covered here: the cell naming and its inverse, the candidate grid, the corridor
polygon filter that narrows it, the corridor being built fresh from a
centerline via lib.corridor.build_corridor() rather than read from any fixed
file (see CENTERLINE_PATH), and write_gate_problems() - the count comparison
that gates main()'s final tile_index.json write.
"""

import pytest

import fetch_elevation
from fetch_elevation import (
    build_tile_index,
    candidate_cells,
    cell_bounds,
    cell_name,
    cell_url,
    corridor_bbox,
)
from tests.synthetic import CENTERLINE_COORDS, write_centerline

# The shared line's 30-mile buffer spans just over 1 degree of longitude
# (verified empirically), so the grid sees more than one cell - which is the
# property this suite tests against.
#
# A short line whose 30-mile buffer fits inside a single 1-degree cell, for
# the other side of that test. Its own, because nothing else needs it.
SMALL_CENTERLINE_COORDS = [(-81.50, 20.00), (-81.49, 20.01)]


def _corridor_bbox_for(path):
    """The corridor's bbox, built fresh from a centerline the way main() does."""

    from lib.corridor import build_corridor
    from tests.conftest import spatial_connection

    con = spatial_connection()
    build_corridor(con, path)
    return corridor_bbox(con)


# --- cell names and their bounds -----------------------------------------


def test_a_cell_is_named_from_its_north_west_corner():
    """USGS's own convention, and the whole reason a URL can be computed.
    n35w084 is the cell whose north-west corner is 35N 84W."""
    assert cell_name(35, 84) == "n35w084"
    assert cell_name(46, 69) == "n46w069"


def test_a_cell_name_is_zero_padded_to_the_width_usgs_uses():
    """Two digits of latitude, three of longitude. A cell named n5w84 exists
    nowhere in the bucket, so an unpadded name is a 404 rather than a miss."""
    assert cell_name(5, 84) == "n05w084"


@pytest.mark.parametrize("north,west", [(0, 84), (-35, 84), (35, 0), (35, -84)])
def test_a_cell_outside_the_north_west_quadrant_is_refused(north, west):
    """The AT is entirely north and west, and a hemisphere this code has never
    seen is better refused than guessed at - a silently wrong hemisphere would
    compute a URL that 404s, which reads as 'no coverage' rather than as a bug."""
    with pytest.raises(ValueError):
        cell_name(north, west)


def test_bounds_come_back_out_of_the_name():
    """The arithmetic that replaced TNM's boundingBox field. A cell extends one
    degree south and one degree east of the corner it is named for."""
    assert cell_bounds("n35w084") == (-84.0, 34.0, -83.0, 35.0)


def test_a_name_and_its_bounds_round_trip():
    """The property that matters more than either direction alone: the bounds
    written into tile_index.json describe the tile the URL beside them fetches.
    A mismatch here would sample the wrong ground and look entirely plausible."""
    for north, west in [(35, 84), (41, 74), (46, 69), (5, 180)]:
        bounds = cell_bounds(cell_name(north, west))
        assert bounds[3] == north
        assert bounds[0] == -west


def test_the_url_is_the_current_edition_rather_than_a_dated_one():
    """The editions hazard, solved upstream. USGS splits current/ from
    historical/, and the TNM catalogue returned both mixed together - which is
    why this file used to need a newest-per-footprint dedup at all."""
    url = cell_url("n35w084")

    assert "/current/n35w084/USGS_13_n35w084.tif" in url
    assert "historical" not in url
    # 1/3 arc-second, not 1 metre - a ~40x change in transfer if it slipped.
    assert "/Elevation/13/TIFF/" in url


# --- candidate_cells: the grid, without a database ------------------------


def test_one_cell_covers_a_bbox_inside_one_cell():
    cells = candidate_cells((-84.6, 34.2, -84.4, 34.4))

    assert cells == ["n35w085"]


def test_a_bbox_spanning_a_boundary_takes_both_cells():
    """The corridor crosses 14 states; missing a cell at a boundary is a
    stretch of trail with no elevation rather than a visible failure."""
    cells = candidate_cells((-84.6, 34.2, -83.4, 34.4))

    # Set rather than sequence: this function's order is an artefact of the
    # loop, and build_tile_index is where the ordering guarantee lives.
    assert set(cells) == {"n35w085", "n35w084"}


def test_every_candidate_cell_actually_overlaps_the_bbox():
    """A superset is fine and a WRONG superset is not: each extra cell is a
    real HTTP range read at sampling time, against a ~460 MB tile."""
    bbox = (-84.73, 34.19, -68.30, 46.34)

    for cell in candidate_cells(bbox):
        west, south, east, north = cell_bounds(cell)
        assert west <= bbox[2] and east >= bbox[0]
        assert south <= bbox[3] and north >= bbox[1]


def test_the_corridor_bbox_produces_cells_covering_both_terminuses():
    """Springer Mountain and Katahdin, which is the end-to-end claim: a grid
    that lost either end would still look like a full corridor in aggregate."""
    cells = candidate_cells((-84.73, 34.19, -68.30, 46.34))

    assert "n35w085" in cells  # Springer Mountain, Georgia
    assert "n46w069" in cells  # Katahdin, Maine


def test_the_grid_needs_no_network_and_no_database():
    """The point of #550, asserted rather than implied. This whole function is
    arithmetic - the version it replaced opened a spatial database, and the one
    before that made 51 HTTP requests that could 504."""
    assert candidate_cells((-84.6, 34.2, -84.4, 34.4)) == ["n35w085"]


# --- build_tile_index: the corridor polygon narrows the grid --------------


def test_a_cell_the_corridor_never_reaches_is_dropped():
    """Filtering on the polygon rather than the rectangle. A 1-degree cell is
    large and the corridor is a 30-mile ribbon, so a cell can clip the
    bounding box in a corner the trail never enters."""
    bbox = (-84.6, 34.2, -83.4, 34.4)

    index = build_tile_index(bbox, corridor_hit=lambda bounds: bounds[0] == -85.0)

    assert [tile["url"] for tile in index] == [cell_url("n35w085")]


def test_each_tile_carries_the_url_and_the_bounds_of_the_same_cell():
    index = build_tile_index((-84.6, 34.2, -84.4, 34.4), corridor_hit=lambda _b: True)

    assert index == [{"url": cell_url("n35w085"), "bounds": [-85.0, 34.0, -84.0, 35.0]}]


def test_the_index_is_sorted_so_two_runs_can_be_diffed():
    """Not cosmetic: it makes tile_index.json a file whose diff shows what
    actually changed, rather than whatever order a catalogue answered in."""
    index = build_tile_index((-84.73, 34.19, -68.30, 46.34), corridor_hit=lambda _b: True)
    names = [tile["url"] for tile in index]

    assert names == sorted(names)


def test_no_cell_appears_twice():
    """A duplicate would be sampled twice and counted twice by the write gate,
    which is the gate measuring its own noise."""
    index = build_tile_index((-84.73, 34.19, -68.30, 46.34), corridor_hit=lambda _b: True)
    urls = [tile["url"] for tile in index]

    assert len(urls) == len(set(urls))


# --- the corridor is built fresh, not read from a stale file --------------


def test_the_corridor_is_built_fresh_from_centerline_path_not_a_stale_file(tmp_path):
    """Regression guard carried over from the TNM version: this module used to
    read the confirmed-stale data/spike/corridor.geojson via a CORRIDOR_PATH
    constant (see lib/corridor.py's docstring for why that file must never be
    read). Two different centerlines must produce two different grids."""
    assert not hasattr(fetch_elevation, "CORRIDOR_PATH")

    small_path = tmp_path / "small.geojson"
    write_centerline(small_path, SMALL_CENTERLINE_COORDS)
    small_cells = candidate_cells(_corridor_bbox_for(small_path))

    wide_path = tmp_path / "wide.geojson"
    write_centerline(wide_path, CENTERLINE_COORDS)
    wide_cells = candidate_cells(_corridor_bbox_for(wide_path))

    assert small_cells != wide_cells


def test_a_corridor_inside_one_cell_still_produces_a_cell(tmp_path):
    """Not zero: the corridor must never be lost entirely, which is the
    failure a bbox-arithmetic bug produces silently."""
    path = tmp_path / "small.geojson"
    write_centerline(path, SMALL_CENTERLINE_COORDS)

    assert len(candidate_cells(_corridor_bbox_for(path))) >= 1


# --- what the TNM path left behind ---------------------------------------


@pytest.mark.parametrize(
    "gone",
    [
        "TNM_API_URL",
        "TNM_BACKOFF_SECONDS",
        "CELL_CACHE_DIR",
        "CELL_CACHE_MAX_AGE_DAYS",
        "list_products_for_cell",
        "cell_products",
        "cell_cache_path",
        "cached_cell_items",
        "compute_grid_cells",
        "_edition_of",
    ],
)
def test_the_discovery_path_is_gone_rather_than_merely_unused(gone):
    """Left in place, these read as a fallback somebody could switch back on,
    and the per-cell cache in particular would look like a live optimisation
    while nothing wrote to it. The workflow step that restored that cache is
    removed in the same change."""
    assert not hasattr(fetch_elevation, gone)


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


# --- stamp_last_modified: keeping the freshness monitor alive -------------


def test_each_tile_gets_the_timestamp_its_url_answered_with():
    index = [{"url": cell_url("n35w084"), "bounds": [-84.0, 34.0, -83.0, 35.0]}]

    fetch_elevation.stamp_last_modified(index, head=lambda _url: "Wed, 15 Feb 2023 00:00:00 GMT")

    assert index[0]["last_modified"] == "Wed, 15 Feb 2023 00:00:00 GMT"


def test_one_request_per_cell_and_no_more():
    """The whole cost of keeping revision detection: one HEAD per cell, no
    pagination, against the bucket the export already streams from."""
    index = [
        {"url": cell_url("n35w084"), "bounds": [-84.0, 34.0, -83.0, 35.0]},
        {"url": cell_url("n36w084"), "bounds": [-84.0, 35.0, -83.0, 36.0]},
    ]
    asked = []

    fetch_elevation.stamp_last_modified(index, head=lambda url: asked.append(url) or "x")

    assert asked == [cell_url("n35w084"), cell_url("n36w084")]


def test_a_failed_head_records_none_rather_than_failing_the_run():
    """The index is still correct without a timestamp - the profile is built
    from the URLs, not from the headers. A network problem costs freshness
    detail and must never cost the elevation data."""
    index = [{"url": cell_url("n35w084"), "bounds": [-84.0, 34.0, -83.0, 35.0]}]

    fetch_elevation.stamp_last_modified(index, head=lambda _url: None)

    assert index[0]["last_modified"] is None
    assert index[0]["url"] == cell_url("n35w084")


def test_stamping_does_not_disturb_the_index_it_was_given():
    """The bounds and URL are what export_elevation.py reads. A stamping step
    that reordered or dropped an entry would be a coverage change disguised
    as a metadata one."""
    index = build_tile_index((-84.6, 34.2, -83.4, 34.4), corridor_hit=lambda _b: True)
    before = [(tile["url"], list(tile["bounds"])) for tile in index]

    fetch_elevation.stamp_last_modified(index, head=lambda _url: "x")

    assert [(tile["url"], list(tile["bounds"])) for tile in index] == before
