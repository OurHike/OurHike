"""NOAA's High-Resolution Rapid Refresh CONUS grid, pinned (#1056, features/WEATHER.md).

HRRR supplies the first two days' temperature, and its cell heights, from which
the phone corrects that temperature to a trail point's own height (WEATHER.md
§3, the maintainer's choice of 2026-09-24). Its grid is not NBM's: 3 km cells
on a different Lambert conformal projection and a slightly different sphere.
So the weather job needs a second answer to "which cell is this point in", and
this module is it. `lib/nbm_grid.py` remains the grid everything is filed by;
HRRR is looked up from NBM square centres.

THE GRID IS PINNED, NOT DISCOVERED, for the reason nbm_grid gives: a future
HRRR that moved its grid would otherwise be sampled at the old cells with
every value plausible. The numbers were read with rasterio from a live HRRR
file on 2026-09-29 (`hrrr.20260929/conus/hrrr.t06z.wrfsfcf24.grib2`, the
`HGT:surface` message): `ds.transform` and `ds.crs.to_proj4()`.

THE DECODE WAS CHECKED AGAINST THE GROUND, because GRIB decoding is where
WEATHER.md §6's mirrored-rows trap lives. HRRR's scanning mode is not NBM's
alternating one, and GDAL's read put the right heights and water in the
right places at every point tried, 2026-09-29:

    Mount Washington   cell (216, 1589)   model height 1,306 m (summit 1,917)   land
    Denver             cell (474, 686)    1,602 m (city 1,609)                   land
    Lake Champlain     cell (222, 1534)   28 m (lake surface ~30)                water
    Atlantic off NJ    cell (394, 1567)   0 m                                    water

`tests/test_lib_hrrr_grid.py` pins those cells to this arithmetic, and
`build_weather_squares.check_hrrr_terrain` refuses a height grid whose Mount
Washington cell is not a mountain.
"""

from __future__ import annotations

import numpy as np
import pyproj

# `+R=6371229` is the sphere HRRR's GRIB declares - not NBM's 6,371,200, and
# not WGS84. Read from the live file named above.
PROJ4 = "+proj=lcc +lat_0=38.5 +lon_0=-97.5 +lat_1=38.5 +lat_2=38.5 +x_0=0 +y_0=0 +R=6371229 +units=m +no_defs"
ORIGIN_X = -2699020.142521929  # west edge of column 0, metres
ORIGIN_Y = 1588193.847443335  # north edge of row 0, metres
CELL_M = 3000.0
WIDTH = 1799
HEIGHT = 1059

# A hundredth of a cell of slack on the origin, and a millimetre on the cell
# size - nbm_grid's tolerances and nbm_grid's reasons, scaled to 3 km.
TOLERANCE_M = CELL_M / 100
CELL_TOLERANCE_M = 1e-3

_TO_GRID = pyproj.Transformer.from_crs("EPSG:4326", PROJ4, always_xy=True)


def cells(lons, lats) -> tuple[np.ndarray, np.ndarray]:
    """(rows, cols) of the HRRR cell containing each point, `-1` for both
    where the point is off the grid."""
    x, y = _TO_GRID.transform(np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))
    fcols = (np.asarray(x) - ORIGIN_X) / CELL_M
    frows = (ORIGIN_Y - np.asarray(y)) / CELL_M
    finite = np.isfinite(fcols) & np.isfinite(frows)
    cols = np.floor(np.where(finite, fcols, -1)).astype(np.int64)
    rows = np.floor(np.where(finite, frows, -1)).astype(np.int64)
    off = (rows < 0) | (rows >= HEIGHT) | (cols < 0) | (cols >= WIDTH) | ~finite
    return np.where(off, -1, rows), np.where(off, -1, cols)


def matches(transform, crs, width: int, height: int) -> bool:
    """True when a raster sits on exactly this grid. `transform` is an affine
    (rasterio's), `crs` anything pyproj accepts."""
    if (width, height) != (WIDTH, HEIGHT):
        return False
    a, b, c, d, e, f = tuple(transform)[:6]
    if b != 0 or d != 0:
        return False
    if abs(a - CELL_M) > CELL_TOLERANCE_M or abs(-e - CELL_M) > CELL_TOLERANCE_M:
        return False
    if abs(c - ORIGIN_X) > TOLERANCE_M or abs(f - ORIGIN_Y) > TOLERANCE_M:
        return False
    return pyproj.CRS.from_user_input(crs).equals(pyproj.CRS.from_proj4(PROJ4), ignore_axis_order=True)
