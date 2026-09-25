"""NOAA's National Blend of Models CONUS grid, pinned (#1056, features/WEATHER.md).

Every NBM forecast field is a raster on one Lambert conformal grid of 2.5 km
squares, and the weather job reads each field at the squares under trail. So
the one question every part of that job asks is "which square is this point
in", and this module is the one place that answers it - the job that samples
the forecast and the phone that will later look a point up must agree about
it to the square, or a hiker reads the forecast for the square next door.

THE GRID IS PINNED, NOT DISCOVERED. The numbers below were read off a live
NBM v5.0 Cloud-Optimized GeoTIFF on 2026-09-24
(`blendv5.0_conus_temp_2026-09-24T09:00_2026-09-24T10:00.tif`, via rasterio's
`ds.transform` and `ds.crs.to_proj4()`), and `matches` refuses any file whose
grid differs. That refusal is the point: NBM's version is already in its
bucket path (`blendv4.3/` became `blendv5.0/` on 2026-05-05), and a future
version that moved the grid would otherwise be sampled at the old squares
with every value plausible and every one of them somewhere else.

WHY A POINT'S SQUARE IS THE SQUARE CONTAINING IT, rather than "the nearest
square centre": on a regular grid they are the same square, and containment
is the formula a phone can run without a search.
"""

from __future__ import annotations

import numpy as np
import pyproj

# Read from the live file named above. `+R=6371200` is the sphere GRIB's
# shape-of-the-earth code 6 means; NBM is not on WGS84, and treating it as if
# it were moves a point by up to ~20 km at these latitudes.
PROJ4 = "+proj=lcc +lat_0=25 +lon_0=-95 +lat_1=25 +lat_2=25 +x_0=0 +y_0=0 +R=6371200 +units=m +no_defs"
ORIGIN_X = -3272421.4573371694  # west edge of column 0, metres
ORIGIN_Y = 3790842.106035436  # north edge of row 0, metres
SQUARE_M = 2539.703
WIDTH = 2345
HEIGHT = 1597

# How close a file's origin must be to the pinned one: a hundredth of a
# square. Not a millimetre, which is what this first said, because two files
# on the same grid do not state its corner identically - measured 2026-09-24,
# URMA's GRIB2 terrain (decoded by GDAL from the first grid point's
# latitude/longitude) sits 4.3 m east and 3.8 m south of the NBM GeoTIFF's
# origin, with square size, shape and projection equal. A hundredth of a
# square (25 m) admits that and still refuses any grid moved by more, which
# is the failure this exists for: a moved grid misses by whole squares.
TOLERANCE_M = SQUARE_M / 100

# The square size gets no such slack. An error in it accumulates across the
# grid - 25 m a square is 58 km by column 2,345 - and every file measured
# states 2539.703 exactly, so a millimetre is the whole of the tolerance.
SQUARE_TOLERANCE_M = 1e-3

_TO_GRID = pyproj.Transformer.from_crs("EPSG:4326", PROJ4, always_xy=True)


def squares(lons, lats) -> tuple[np.ndarray, np.ndarray]:
    """(rows, cols) of the square containing each point, `-1` for both where
    the point is off the grid - Alaska, Puerto Rico and Hawaii are separate
    NBM grids this module does not describe."""
    x, y = _TO_GRID.transform(np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))
    cols = np.floor((np.asarray(x) - ORIGIN_X) / SQUARE_M).astype(np.int64)
    rows = np.floor((ORIGIN_Y - np.asarray(y)) / SQUARE_M).astype(np.int64)
    off = (rows < 0) | (rows >= HEIGHT) | (cols < 0) | (cols >= WIDTH) | ~np.isfinite(x) | ~np.isfinite(y)
    rows = np.where(off, -1, rows)
    cols = np.where(off, -1, cols)
    return rows, cols


def matches(transform, crs, width: int, height: int) -> bool:
    """True when a raster sits on exactly this grid.

    `transform` is an affine (rasterio's), `crs` anything pyproj accepts.
    Every field the job reads is checked with this before a value leaves it.
    """
    if (width, height) != (WIDTH, HEIGHT):
        return False
    a, b, c, d, e, f = tuple(transform)[:6]
    if b != 0 or d != 0:
        return False
    if abs(a - SQUARE_M) > SQUARE_TOLERANCE_M or abs(-e - SQUARE_M) > SQUARE_TOLERANCE_M:
        return False
    if abs(c - ORIGIN_X) > TOLERANCE_M or abs(f - ORIGIN_Y) > TOLERANCE_M:
        return False
    return pyproj.CRS.from_user_input(crs).equals(pyproj.CRS.from_proj4(PROJ4), ignore_axis_order=True)
