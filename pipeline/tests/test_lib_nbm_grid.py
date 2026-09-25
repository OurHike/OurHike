"""Tests for lib/nbm_grid.py (#1056).

The squares below were read with GDAL's own `ds.index` from a live NBM v5.0
GeoTIFF on 2026-09-24, so this pins our projection arithmetic to the
reader's - the agreement the phone and the job both depend on."""

import pytest
from rasterio.transform import Affine

from lib import nbm_grid

PINNED_BY_GDAL = {
    "Mount Washington summit": ((-71.3033, 44.2706), (562, 2074)),
    "Pinkham Notch": ((-71.2531, 44.2575), (563, 2076)),
    "Lakes of the Clouds Hut": ((-71.3190, 44.2587), (563, 2073)),
    "Bear Mountain, NY (published waypoint)": ((-73.9884, 41.3120), (712, 2007)),
    "Springer Mountain": ((-84.1936, 34.6272), (1053, 1683)),
}


@pytest.mark.parametrize("name", sorted(PINNED_BY_GDAL))
def test_a_point_lands_in_the_square_gdal_puts_it_in(name):
    (lon, lat), expected = PINNED_BY_GDAL[name]

    rows, cols = nbm_grid.squares([lon], [lat])

    assert (int(rows[0]), int(cols[0])) == expected


def test_three_points_in_the_whites_land_in_three_different_squares():
    # The #1056 case: Lakes of the Clouds and Pinkham Notch are 3.3 miles
    # apart with a 9.2 F disagreement between them. A grid that merged them
    # would answer that disagreement by averaging it away.
    points = [PINNED_BY_GDAL[n][0] for n in ("Mount Washington summit", "Pinkham Notch", "Lakes of the Clouds Hut")]

    rows, cols = nbm_grid.squares([p[0] for p in points], [p[1] for p in points])

    assert len(set(zip(rows.tolist(), cols.tolist(), strict=True))) == 3


def test_a_point_off_the_conus_grid_has_no_square():
    rows, cols = nbm_grid.squares([-149.9, -66.1], [61.2, 18.2])  # Anchorage, Puerto Rico

    assert rows.tolist() == [-1, -1] and cols.tolist() == [-1, -1]


PINNED = Affine(nbm_grid.SQUARE_M, 0, nbm_grid.ORIGIN_X, 0, -nbm_grid.SQUARE_M, nbm_grid.ORIGIN_Y)


def test_the_pinned_grid_matches_itself():
    assert nbm_grid.matches(PINNED, nbm_grid.PROJ4, nbm_grid.WIDTH, nbm_grid.HEIGHT)


def test_a_grid_stated_a_few_metres_off_still_matches():
    # URMA's GRIB2 terrain, measured 2026-09-24: 4.3 m east, 3.8 m south.
    shifted = Affine(nbm_grid.SQUARE_M, 0, nbm_grid.ORIGIN_X + 4.3, 0, -nbm_grid.SQUARE_M, nbm_grid.ORIGIN_Y - 3.8)

    assert nbm_grid.matches(shifted, nbm_grid.PROJ4, nbm_grid.WIDTH, nbm_grid.HEIGHT)


def test_a_grid_moved_by_a_square_is_refused():
    moved = Affine(nbm_grid.SQUARE_M, 0, nbm_grid.ORIGIN_X + nbm_grid.SQUARE_M, 0, -nbm_grid.SQUARE_M, nbm_grid.ORIGIN_Y)

    assert not nbm_grid.matches(moved, nbm_grid.PROJ4, nbm_grid.WIDTH, nbm_grid.HEIGHT)


def test_a_square_one_metre_bigger_is_refused():
    # A metre a square is 2.3 km by the last column: a different grid.
    bigger = Affine(nbm_grid.SQUARE_M + 1, 0, nbm_grid.ORIGIN_X, 0, -(nbm_grid.SQUARE_M + 1), nbm_grid.ORIGIN_Y)

    assert not nbm_grid.matches(bigger, nbm_grid.PROJ4, nbm_grid.WIDTH, nbm_grid.HEIGHT)


def test_a_different_shape_or_projection_is_refused():
    assert not nbm_grid.matches(PINNED, nbm_grid.PROJ4, nbm_grid.WIDTH - 1, nbm_grid.HEIGHT)
    assert not nbm_grid.matches(PINNED, "EPSG:4326", nbm_grid.WIDTH, nbm_grid.HEIGHT)
