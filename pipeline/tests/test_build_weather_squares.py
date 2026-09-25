"""Tests for build_weather_squares.py's pure pieces (#1056).

The network half (the release, URMA's terrain) is exercised by running the
script; what is pinned here is the arithmetic every published square rests
on - where points are laid, which cell a square is filed under, and which
water square borrows which land."""

import json

import numpy as np
import pytest

import build_weather_squares as squares_mod
from lib import nbm_grid


def test_densify_lays_points_no_further_apart_than_the_step():
    line = np.array([[-80.0, 40.0], [-79.9, 40.05]])

    points = squares_mod.densify(line, step_deg=0.004)

    gaps = np.abs(np.diff(points, axis=0)).max(axis=1)
    assert gaps.max() <= 0.004 + 1e-12
    assert points[0].tolist() == [-80.0, 40.0] and points[-1].tolist() == [-79.9, 40.05]


def test_densify_leaves_a_single_vertex_alone():
    assert squares_mod.densify(np.array([[-80.0, 40.0]])).tolist() == [[-80.0, 40.0]]


def test_a_line_through_a_square_is_found_even_when_no_vertex_is_in_it():
    # Two vertices ~11 km apart; the squares between them hold no vertex.
    line = np.array([[-71.40, 44.27], [-71.26, 44.27]])
    points = squares_mod.densify(line)

    cells, _ = squares_mod.squares_by_cell(points[:, 0], points[:, 1])

    found = {tuple(sq) for sq in cells["n44w072"]}
    ends = {(int(r), int(c)) for r, c in zip(*nbm_grid.squares(line[:, 0], line[:, 1]), strict=True)}
    assert ends <= found and len(found) >= 5


def test_a_square_is_filed_under_every_cell_a_trail_point_in_it_falls_in():
    # Straddling the 72nd meridian: one point each side.
    lons, lats = np.array([-72.001, -71.999]), np.array([44.5, 44.5])

    cells, _ = squares_mod.squares_by_cell(lons, lats)

    assert set(cells) == {"n44w073", "n44w072"}


def test_a_point_off_the_conus_grid_is_listed_rather_than_dropped():
    lons, lats = np.array([-149.9, -71.3033]), np.array([61.2, 44.2706])

    cells, outside = squares_mod.squares_by_cell(lons, lats)

    assert outside == ["n61w150"]
    assert cells == {"n44w072": [[562, 2074]]}


def test_geometry_lines_reads_both_line_types_and_ignores_the_rest():
    line = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
    multi = {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}

    assert squares_mod.geometry_lines(line) == [[[0, 0], [1, 1]]]
    assert len(squares_mod.geometry_lines(multi)) == 2
    assert squares_mod.geometry_lines({"type": "Point", "coordinates": [0, 0]}) == []
    assert squares_mod.geometry_lines(None) == []


def terrain_with(values: dict[tuple[int, int], float], default: float = 100.0) -> np.ndarray:
    grid = np.full((20, 20), default)
    for square, height in values.items():
        grid[square] = height
    return grid


def test_a_water_square_borrows_its_nearest_land_square():
    # Bear Mountain, in miniature: the waypoint's square is river at 0 m and
    # the square north of it is land (measured: (711, 2007) at 41 m).
    terrain = terrain_with({(10, 10): 0.0, (10, 11): 0.0, (11, 10): 0.0, (11, 11): 0.0, (10, 9): 0.0})

    borrowed, kept = squares_mod.borrow_land({(10, 10)}, terrain)

    assert borrowed == {(10, 10): (9, 10)}  # distance 1, and the smallest (row, col) of the ties
    assert kept == []


def test_a_land_square_reads_its_own_forecast():
    borrowed, kept = squares_mod.borrow_land({(5, 5)}, terrain_with({}))

    assert borrowed == {} and kept == []


def test_open_water_with_no_land_in_reach_keeps_its_own_and_is_listed():
    terrain = terrain_with({}, default=0.0)
    terrain[0, 0] = 50.0  # far outside two squares of (10, 10)

    borrowed, kept = squares_mod.borrow_land({(10, 10)}, terrain)

    assert borrowed == {} and kept == [(10, 10)]


def test_a_mountain_where_mount_washington_is_passes_the_terrain_check():
    terrain = np.zeros((nbm_grid.HEIGHT, nbm_grid.WIDTH), dtype=np.float32)
    terrain[562, 2074] = 1702.0

    squares_mod.check_terrain(terrain)


def test_a_mirrored_terrain_grid_is_refused():
    # The first trap in WEATHER.md §6: rows reversed, and the mountain lands
    # somewhere else entirely.
    terrain = np.zeros((nbm_grid.HEIGHT, nbm_grid.WIDTH), dtype=np.float32)
    terrain[562, 2074] = 1702.0

    with pytest.raises(RuntimeError, match="Mount Washington"):
        squares_mod.check_terrain(terrain[::-1, :])


def test_a_cached_index_is_reused_only_for_its_own_release_and_schema(tmp_path, monkeypatch):
    path = tmp_path / "squares.json"
    monkeypatch.setattr(squares_mod, "SQUARES_PATH", path)

    assert squares_mod.cached_release() is None

    path.write_text(json.dumps({"schema": squares_mod.SCHEMA, "release": "2026-09-24-4"}))
    assert squares_mod.cached_release() == "2026-09-24-4"

    path.write_text(json.dumps({"schema": squares_mod.SCHEMA - 1, "release": "2026-09-24-4"}))
    assert squares_mod.cached_release() is None
