"""Unit tests for the hand-rolled Web Mercator XYZ tile math in lib/tiling.py."""
import pytest

from lib.tiling import WEB_MERCATOR_HALF_WORLD, tile_bounds_merc, tile_range_for_bounds

R = WEB_MERCATOR_HALF_WORLD


def test_zoom_zero_tile_covers_the_whole_world():
    assert tile_bounds_merc(0, 0, 0) == pytest.approx((-R, -R, R, R))


@pytest.mark.parametrize("x, y, expected", [
    (0, 0, (-R, 0, 0, R)),   # northwest quadrant
    (1, 0, (0, 0, R, R)),    # northeast quadrant
    (0, 1, (-R, -R, 0, 0)),  # southwest quadrant
    (1, 1, (0, -R, R, 0)),   # southeast quadrant
])
def test_zoom_one_quadrants(x, y, expected):
    assert tile_bounds_merc(1, x, y) == pytest.approx(expected)


def test_tile_range_for_whole_world_bounds_matches_full_grid():
    n = 2**3
    assert tile_range_for_bounds((-R, -R, R, R), 3) == (0, n - 1, 0, n - 1)


def test_tile_range_for_a_single_known_tile_bounds_returns_that_tile():
    z, x, y = 8, 73, 96
    bounds = tile_bounds_merc(z, x, y)
    # Shrink slightly so we're unambiguously inside this tile, not touching a neighbor.
    minx, miny, maxx, maxy = bounds
    pad_x, pad_y = (maxx - minx) * 0.1, (maxy - miny) * 0.1
    shrunk = (minx + pad_x, miny + pad_y, maxx - pad_x, maxy - pad_y)
    assert tile_range_for_bounds(shrunk, z) == (x, x, y, y)


def test_tile_range_clamps_to_valid_grid_at_the_edges():
    z = 4
    n = 2**z
    # A bbox far outside the world extent should clamp to the grid's edge, not go negative or past n-1.
    x0, x1, y0, y1 = tile_range_for_bounds((-R * 5, -R * 5, R * 5, R * 5), z)
    assert (x0, x1, y0, y1) == (0, n - 1, 0, n - 1)
