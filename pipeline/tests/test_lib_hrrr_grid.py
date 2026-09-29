"""Tests for lib/hrrr_grid.py (#1056, the HRRR slice).

The cells below are where GDAL's read of a live HRRR file (2026-09-29, the
06Z run) put the right height and the right land or water - see the module
docstring's table - so this pins our projection arithmetic to that read."""

import pytest
from rasterio.transform import Affine

from lib import hrrr_grid

PINNED = {
    "Mount Washington summit": ((-71.3033, 44.2706), (216, 1589)),
    "Denver": ((-104.99, 39.74), (474, 686)),
    "Lake Champlain": ((-73.33, 44.50), (222, 1534)),
    "Atlantic off New Jersey": ((-73.80, 39.80), (394, 1567)),
    "Springer Mountain": ((-84.1936, 34.6272), (643, 1305)),
}


@pytest.mark.parametrize("name", sorted(PINNED))
def test_a_point_lands_in_the_cell_gdal_read_it_from(name):
    (lon, lat), expected = PINNED[name]

    rows, cols = hrrr_grid.cells([lon], [lat])

    assert (int(rows[0]), int(cols[0])) == expected


def test_the_summit_and_lakes_of_the_clouds_are_different_hrrr_cells():
    # 1.3 km apart and 110 m of HRRR height apart (1,306 against 1,419 m): the
    # correction has to start from each point's own cell.
    rows, cols = hrrr_grid.cells([-71.3033, -71.3190], [44.2706, 44.2587])

    assert (int(rows[0]), int(cols[0])) != (int(rows[1]), int(cols[1]))


def test_a_point_off_the_grid_has_no_cell():
    rows, cols = hrrr_grid.cells([-149.9, -66.1], [61.2, 18.2])  # Anchorage, Puerto Rico

    assert rows.tolist() == [-1, -1] and cols.tolist() == [-1, -1]


GRID = Affine(hrrr_grid.CELL_M, 0, hrrr_grid.ORIGIN_X, 0, -hrrr_grid.CELL_M, hrrr_grid.ORIGIN_Y)


def test_the_pinned_grid_matches_itself():
    assert hrrr_grid.matches(GRID, hrrr_grid.PROJ4, hrrr_grid.WIDTH, hrrr_grid.HEIGHT)


def test_a_grid_moved_by_a_cell_is_refused():
    moved = Affine(hrrr_grid.CELL_M, 0, hrrr_grid.ORIGIN_X + hrrr_grid.CELL_M, 0, -hrrr_grid.CELL_M, hrrr_grid.ORIGIN_Y)

    assert not hrrr_grid.matches(moved, hrrr_grid.PROJ4, hrrr_grid.WIDTH, hrrr_grid.HEIGHT)


def test_nbms_grid_is_not_hrrrs():
    from lib import nbm_grid

    nbm = Affine(nbm_grid.SQUARE_M, 0, nbm_grid.ORIGIN_X, 0, -nbm_grid.SQUARE_M, nbm_grid.ORIGIN_Y)

    assert not hrrr_grid.matches(nbm, nbm_grid.PROJ4, nbm_grid.WIDTH, nbm_grid.HEIGHT)
    # The same shape and transform on NBM's sphere is still refused.
    assert not hrrr_grid.matches(GRID, nbm_grid.PROJ4, hrrr_grid.WIDTH, hrrr_grid.HEIGHT)
