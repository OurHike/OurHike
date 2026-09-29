"""Tests for lib/batch_geometry.py - the whole-array versions of the per-record
parse, reproject and round steps the line exporters publish through (#1661).
Every test holds a batch function to the per-record step it replaced, to the
bit, because the published files are compared by hash. Synthetic geometry
only; never real data.
"""

import random

import numpy as np
import pytest
from pyproj import Transformer
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, MultiLineString
from shapely.ops import transform as shapely_ops_transform

from lib.batch_geometry import from_wkt_all, reproject, round_like_python
from lib.corridor import GEOGRAPHIC_CRS, PROJECTED_CRS

_TO_METRIC = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True).transform
_TO_GEOGRAPHIC = Transformer.from_crs(PROJECTED_CRS, GEOGRAPHIC_CRS, always_xy=True).transform


def _wandering_lines(seed: int, count: int) -> list:
    """LineStrings and MultiLineStrings around Harriman, in lon/lat, with
    full-precision coordinates like the raw layers carry."""
    rng = random.Random(seed)

    def line():
        lon, lat = rng.uniform(-74.3, -73.9), rng.uniform(41.0, 41.4)
        coords = []
        for _ in range(rng.randint(2, 60)):
            lon += rng.uniform(-0.001, 0.001)
            lat += rng.uniform(-0.001, 0.001)
            coords.append((lon, lat))
        return LineString(coords)

    return [line() if n % 3 else MultiLineString([line(), line()]) for n in range(count)]


def test_from_wkt_all_parses_what_loads_parses_without_sizing_every_row_by_the_longest():
    """Handed a plain list of str, numpy sizes the array by the longest string
    for every row: here one 183,897-character WKT among a thousand short
    ones, 1,001 x 183,897 x 4 bytes, ~0.74 GB. tracemalloc sees numpy's
    allocations, so the peak is what this holds, not the timing."""
    import tracemalloc

    lines = _wandering_lines(1661, 1000)
    long_line = LineString([(-74.0 + n * 1e-6, 41.0 + (n % 2) * 1e-6) for n in range(10_000)])
    wkts = [line.wkt for line in lines] + [long_line.wkt]

    tracemalloc.start()
    try:
        parsed = from_wkt_all(wkts)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < 50_000_000
    assert parsed.dtype == object and parsed.shape == (len(wkts),)
    assert [geom.wkt for geom in parsed] == [shapely_wkt.loads(wkt).wkt for wkt in wkts]
    assert from_wkt_all([]).shape == (0,)


def test_reproject_answers_what_ops_transform_answers_to_the_bit():
    geoms = np.array(_wandering_lines(1661, 500) + [LineString()], dtype=object)

    there = reproject(geoms, _TO_METRIC)
    back = reproject(there, _TO_GEOGRAPHIC)

    assert [g.wkt for g in there] == [shapely_ops_transform(_TO_METRIC, g).wkt for g in geoms]
    assert [g.wkt for g in back] == [shapely_ops_transform(_TO_GEOGRAPHIC, g).wkt for g in there]


def test_reproject_hands_a_geometry_with_z_to_ops_transform_and_keeps_its_z():
    """shapely.transform would drop the Z, or hand the transform NaN for a 2D
    neighbour's missing one. Neither is what the per-record step did."""
    flat = LineString([(-74.0, 41.0), (-74.01, 41.01)])
    raised = LineString([(-74.0, 41.0, 300.0), (-74.01, 41.01, 320.0)])
    geoms = np.array([flat, raised], dtype=object)

    out = reproject(geoms, _TO_METRIC)

    assert out[1].has_z and not out[0].has_z
    assert [g.wkt for g in out] == [shapely_ops_transform(_TO_METRIC, g).wkt for g in geoms]


@pytest.mark.parametrize("decimals", [6, 4])
def test_round_like_python_answers_what_pythons_round_answers_including_at_the_half(decimals):
    rng = random.Random(1659 + decimals)
    scale = 10**decimals
    values = [rng.uniform(-180, 180) for _ in range(200_000)]
    # Values built to sit on the edge the fast path hands back to Python:
    # an exact half in the last kept decimal, nudged a few ulps either way.
    for _ in range(20_000):
        half = (rng.randrange(-180 * scale, 180 * scale) + 0.5) / scale
        # float(), because Python's round on a numpy float uses numpy's rounding,
        # which would make the reference below the thing under test.
        values.extend([half, float(np.nextafter(half, 1e9)), float(np.nextafter(half, -1e9))])
    values.extend([0.0, -0.0, 4e-7, -4e-7, 5e-7, -5e-7, 1.5e-6, -74.1234565, 41.2500005, 1e300, -1e300])

    rounded = round_like_python(np.asarray(values, dtype=float), decimals).tolist()

    assert rounded == [round(value, decimals) for value in values]
    assert [str(value) for value in rounded] == [str(round(value, decimals)) for value in values], "including the sign of zero"


def test_round_like_python_refuses_a_precision_it_cannot_promise():
    with pytest.raises(ValueError):
        round_like_python(np.array([1.0]), 16)
    with pytest.raises(ValueError):
        round_like_python(np.array([1.0]), -1)
