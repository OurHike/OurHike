"""Whole-array versions of three per-record geometry steps (#1661).

The line exporters parse a WKT, reproject it and round its coordinates one
record at a time, and on the real network that is 142,892 records and
22,000,055 coordinates per pass (measured 2026-09-24). Each function here
does one of those steps for every record at once and returns exactly what
the per-record step returns - the same doubles, not nearby ones - because
the published files are compared by hash and a changed last digit is a
changed artifact. tests/test_lib_batch_geometry.py holds each one to its
per-record original.

WKT parsing and writing get no faster on threads (12.3 s against 13.2 s to
parse the network on four, 2026-09-24), so nothing here uses lib/cores.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import shapely
from shapely.ops import transform as shapely_ops_transform


def from_wkt_all(wkts: Sequence[str]) -> np.ndarray:
    """`shapely.wkt.loads` for every string, as one object array.

    The object dtype is the point. Handed a plain list of str, numpy first
    builds a fixed-width unicode array as wide as the LONGEST string, for
    every row: the real network's longest WKT is 1,283,014 characters, and
    that array asked for 683 GiB (2026-09-24)."""
    array = np.empty(len(wkts), dtype=object)
    array[:] = list(wkts)
    return shapely.from_wkt(array)


def reproject(geoms: np.ndarray, transform: Callable) -> np.ndarray:
    """`shapely.ops.transform(transform, geom)` for every geometry, with one
    call to `transform` for all their coordinates. `transform` is a pyproj
    `Transformer.transform`, or anything else taking and returning (x, y)
    arrays; PROJ transforms each point on its own, so the batch changes no
    answer.

    A geometry with Z goes through `shapely.ops.transform` itself.
    `shapely.transform` either drops the third dimension or, asked to keep
    it, hands the function NaN for a 2D geometry's missing one, and neither
    is what the per-record step did. No record on the real network has Z
    (2026-09-24), so this is the path that is never taken, kept so that one
    arriving cannot change an answer silently."""
    out = shapely.transform(geoms, transform, interleaved=False)
    has_z = shapely.has_z(geoms)
    if has_z.any():
        out[has_z] = [shapely_ops_transform(transform, geom) for geom in geoms[has_z]]
    return out


def round_like_python(values: np.ndarray, decimals: int) -> np.ndarray:
    """`round(value, decimals)` for every value, as Python rounds it, without
    one Python call per value (for 20.6 million coordinates, 11.6 s against
    2.6 s, measured 2026-09-24 in build_trail_graph.py).

    WHY NOT JUST `np.round`. Python rounds the exact decimal value of the
    float. Numpy multiplies by 10**decimals first, and the product is itself
    rounded, so a value whose exact product lies within a hair of a half can
    be pushed across it and come out one unit in the last place different -
    a changed coordinate in a published artifact. Everywhere else the two
    agree exactly: the integer is the same, and dividing it by 10**decimals
    gives the nearest double to that decimal, which is also what Python
    returns. So the values whose product lands near a half are handed to
    Python's `round` itself: within 1e-6 of it, or within 2**-50 of the
    product's own size where that is wider, so the margin always exceeds the
    product's rounding error. On the real trail graph that was 76 of
    20,579,500 values at six decimals, and the test suite holds the result
    to `round` on values built to sit on that edge.
    """
    if not 0 <= decimals <= 15:
        raise ValueError(f"decimals must be 0-15, got {decimals}")
    scale = 10.0**decimals
    scaled = values * scale
    rounded = np.rint(scaled) / scale
    margin = np.maximum(1e-6, np.abs(scaled) * 2.0**-50)
    near_half = np.abs((scaled - np.floor(scaled)) - 0.5) < margin
    if near_half.any():
        rounded[near_half] = [round(value, decimals) for value in values[near_half].tolist()]
    return rounded
