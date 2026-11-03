"""Tests for trail-geometry simplification (see export_trails.simplify_records).

Why this exists at all, and why 1 metre: see the long rationale block at the
top of ``simplify_records`` in export_trails.py. The short version is that the
unsimplified corridor export is ~31 MB of GeoJSON across 772,603 coordinates,
which a phone has to parse on every map load, and roughly three quarters of
those vertices are finer than a single screen pixel at any zoom OurHike ships.

The tests below fall into two groups, and the second group is the important
one:

**Does it shrink the file?** - one test, easily satisfied.

**Does it shrink it without losing anything?** - everything else. This
pipeline has already produced one silent data-loss bug of exactly this shape
(3 real MultiLineString centerline features dropped during an earlier export,
which would have erased trail mileage without any error). Simplification is a
lossy step applied to safety-relevant geometry, so the guards here are
deliberately paranoid: no feature disappears, no line degenerates, endpoints
never move, and no vertex is displaced further than the tolerance allows.
"""

import math

import pytest
from shapely.geometry import LineString, MultiLineString, shape

from export_trails import (
    DEFAULT_SIMPLIFY_TOLERANCE_M,
    _has_drawable_geometry,
    simplify_records,
)


def _record(geometry, record_id="t1"):
    return {
        "id": record_id,
        "source": "centerline",
        "name": "Appalachian Trail",
        "blaze_color": "White",
        "wkt": shape(geometry).wkt,
    }


def _dense_line(points=400, meander_m=12.0):
    """A densely-sampled meandering line - the real shape of a GPS-surveyed
    centerline: genuine trail curvature at the scale of metres, sampled far
    more finely than that curvature needs.

    The meander amplitude matters. An almost-straight line collapses to its
    two endpoints at every tolerance, which would make the tolerance-
    comparison tests below pass or fail for reasons unrelated to what they
    are checking.
    """
    coords = []
    for i in range(points):
        # ~1 m spacing north-south, with a metre-scale east-west meander.
        lat = 40.0 + i * (1.0 / 111_320.0)
        lon = -78.0 + math.sin(i / 8.0) * (meander_m / 85_000.0)
        coords.append((lon, lat))
    return LineString(coords)


def _coord_count(record):
    geom = shape_from_wkt(record["wkt"])
    if geom.geom_type == "LineString":
        return len(geom.coords)
    return sum(len(part.coords) for part in geom.geoms)


def shape_from_wkt(wkt):
    from shapely import wkt as shapely_wkt

    return shapely_wkt.loads(wkt)


# --- It shrinks the file -------------------------------------------------


def test_simplify_removes_vertices_finer_than_the_tolerance():
    records = [_record(_dense_line())]

    [out] = simplify_records(records)

    assert _coord_count(out) < _coord_count(records[0])


# --- It shrinks it without losing anything -------------------------------


def test_simplify_never_drops_a_feature():
    """The failure mode this pipeline has already had once: geometry silently
    vanishing from an export. A missing centerline feature is missing trail
    mileage, with nothing to indicate anything went wrong."""
    records = [_record(_dense_line(), f"t{i}") for i in range(25)]

    assert len(simplify_records(records)) == len(records)


def test_simplify_keeps_a_multilinestring_as_a_multilinestring():
    """Exactly the shape of the earlier drop: 3 real MultiLineString
    centerline features lost during an export."""
    multi = MultiLineString([_dense_line(50), _dense_line(50)])

    [out] = simplify_records([_record(multi)])

    assert shape_from_wkt(out["wkt"]).geom_type == "MultiLineString"


def test_simplify_keeps_every_part_of_a_multilinestring():
    multi = MultiLineString([_dense_line(50), _dense_line(50), _dense_line(50)])

    [out] = simplify_records([_record(multi)])

    assert len(shape_from_wkt(out["wkt"]).geoms) == 3


def test_simplify_never_degenerates_a_line_below_two_points():
    """A line collapsed to a single point renders as nothing at all - the
    worst outcome, since it looks like clean output."""
    records = [_record(_dense_line(points=3))]

    [out] = simplify_records(records, tolerance_m=1000)

    assert _coord_count(out) >= 2


def test_a_zero_length_line_is_not_drawable():
    """The bug the "below two points" case above was written to catch and did
    not (#950).

    That guard was implemented as a COORDINATE count, and the collapse it has
    to catch does not reduce the count. Douglas-Peucker never drops an
    endpoint, so a simplified line always has at least two coordinates - but
    simplify_records projects to EPSG:5070 and back, and on a line whose whole
    length is around a metre the two endpoints can round to the SAME
    coordinate on the return trip. The result is a two-coordinate LineString
    of zero length: it passes a coordinate count, it is not empty, and it
    renders as nothing at all.

    Found the day another organization's layer went through the same
    function: measured 2026-08-24 on NYS OPRHP's 16,641-segment layer, five
    exported features came out with zero-length geometry - two of them whole
    trails, "Blueberry Run" at 1.2 m end to end and "Goat Trail" at 0.2 m.
    Both would have vanished from the map with the run reporting success,
    which is exactly the failure this file's header calls "the worst outcome,
    since it looks like clean output". Re-exported after this fix: zero.

    Whether it ever did this to the A.T. is unmeasured - see
    export_trails._drawable_part for why that is an open question rather than
    a settled no.

    Tested against the predicate rather than through simplify_records,
    deliberately. Reproducing the collapse end to end needs a geometry whose
    endpoints happen to round together on a particular platform's float maths,
    which is a test that would pass for reasons nobody could read. The
    predicate is what was wrong and is what this pins.
    """
    point = (-74.0, 41.0)

    assert not _has_drawable_geometry(LineString([point, point]))
    assert _has_drawable_geometry(LineString([point, (-74.0, 41.000009)]))


def test_a_multilinestring_falls_back_whole_when_any_part_is_zero_length():
    """ALL parts, not any - so a MultiLineString with one collapsed part keeps
    its original geometry entirely rather than being published with a gap in
    it. Three of the five real collapses found on OPRHP's layer were this
    shape."""
    point = (-74.0, 41.0)
    real = LineString([point, (-74.0, 41.000009)])
    collapsed = LineString([point, point])

    assert _has_drawable_geometry(MultiLineString([real, real]))
    assert not _has_drawable_geometry(MultiLineString([real, collapsed]))


def test_simplify_preserves_both_endpoints_exactly():
    """Trail ends are junctions, trailheads and shelter approaches. Moving one
    even slightly detaches it from whatever it connects to."""
    line = _dense_line()
    [out] = simplify_records([_record(line)])

    simplified = shape_from_wkt(out["wkt"])
    assert simplified.coords[0] == pytest.approx(line.coords[0], abs=1e-9)
    assert simplified.coords[-1] == pytest.approx(line.coords[-1], abs=1e-9)


def test_simplify_never_moves_the_line_further_than_the_tolerance():
    """The guarantee that makes this safe. Douglas-Peucker bounds displacement
    by the tolerance, so a hiker's rendered position relative to the trail
    cannot shift by more than a metre."""
    line = _dense_line()
    [out] = simplify_records([_record(line)], tolerance_m=1.0)

    simplified = shape_from_wkt(out["wkt"])
    # Hausdorff distance in degrees, converted back to metres at this
    # latitude. Generous ceiling: the point is that it is bounded and small,
    # not that it hits a precise figure.
    displacement_m = line.hausdorff_distance(simplified) * 111_320.0
    assert displacement_m <= 1.5


def test_simplify_keeps_every_property_untouched():
    records = [_record(_dense_line())]

    [out] = simplify_records(records)

    for key in ("id", "source", "name", "blaze_color"):
        assert out[key] == records[0][key]


def test_simplify_leaves_an_already_sparse_line_alone():
    """Nothing redundant means nothing removed.

    The vertices are deliberately NOT collinear. A midpoint sitting exactly on
    the line between its neighbours carries no shape, and Douglas-Peucker
    removing it is correct rather than lossy - so a collinear fixture would
    test the opposite of what this is about.
    """
    sparse = LineString([(-78.0, 40.0), (-77.5, 40.5), (-78.0, 41.0)])

    [out] = simplify_records([_record(sparse)])

    assert _coord_count(out) == 3


def test_simplify_handles_an_empty_export():
    assert simplify_records([]) == []


# --- The tolerance itself ------------------------------------------------


def test_default_tolerance_is_one_metre():
    """Chosen deliberately - see the rationale in export_trails.py. A change
    here is a change to what ships, so it should be a visible edit."""
    assert DEFAULT_SIMPLIFY_TOLERANCE_M == 1.0


def test_default_tolerance_stays_under_one_screen_pixel_at_max_zoom():
    """The property that makes 1 m invisible rather than merely small. At
    z13 - the deepest archive OurHike ships - one 512px tile pixel covers
    roughly 9.5 m of ground at AT latitudes."""
    ground_metres_per_pixel_at_z13 = 9.5

    assert DEFAULT_SIMPLIFY_TOLERANCE_M < ground_metres_per_pixel_at_z13


def test_a_larger_tolerance_removes_more():
    records = [_record(_dense_line())]

    coarse = simplify_records(records, tolerance_m=5.0)
    fine = simplify_records(records, tolerance_m=0.5)

    assert _coord_count(coarse[0]) < _coord_count(fine[0])


def test_a_zero_tolerance_changes_nothing():
    """An explicit escape hatch: 0 means "give me the source geometry", so a
    future consumer that needs full precision has a supported way to ask."""
    records = [_record(_dense_line())]

    [out] = simplify_records(records, tolerance_m=0)

    assert _coord_count(out) == _coord_count(records[0])


def test_simplify_rejects_a_negative_tolerance():
    with pytest.raises(ValueError):
        simplify_records([_record(_dense_line())], tolerance_m=-1)


# --- the batch form (#1661) ---------------------------------------------------
#
# simplify_records runs its parse, reprojection, simplification and WKT as one
# array call each, and the drawable check as _drawable_all. The published
# files are compared by hash, so these hold the batch to the per-record loop it
# replaced to the character, not to a tolerance.


def _simplify_one_record_at_a_time(records, tolerance_m):
    """simplify_records as it was before #1661: one parse, two ops.transform
    calls, one simplify and one .wkt per record."""
    from shapely import wkt as shapely_wkt
    from shapely.ops import transform as shapely_transform

    from export_trails import _TO_GEOGRAPHIC, _TO_METRIC

    simplified = []
    for record in records:
        geom = shapely_wkt.loads(record["wkt"])
        reduced = shapely_transform(
            _TO_GEOGRAPHIC,
            shapely_transform(_TO_METRIC, geom).simplify(tolerance_m, preserve_topology=False),
        )
        if reduced.is_empty or not _has_drawable_geometry(reduced):
            reduced = geom
        simplified.append({**record, "wkt": reduced.wkt})
    return simplified


def _awkward_lines(seed):
    """Wandering lines at full precision, lines short enough to collapse at
    1 m, a MultiLineString with one collapsing part, and a line with Z."""
    import random

    rng = random.Random(seed)

    def wander(steps, step_deg):
        lon, lat = rng.uniform(-74.3, -73.9), rng.uniform(41.0, 41.4)
        coords = [(lon, lat)]
        for _ in range(steps):
            lon += rng.uniform(-step_deg, step_deg)
            lat += rng.uniform(-step_deg, step_deg)
            coords.append((lon, lat))
        return LineString(coords)

    geoms = []
    for n in range(400):
        if n % 5 == 0:
            geoms.append(MultiLineString([wander(rng.randint(1, 50), 0.0005), wander(rng.randint(1, 50), 0.0005)]))
        elif n % 7 == 0:
            geoms.append(wander(rng.randint(1, 4), 0.000002))  # a few centimetres: collapses at 1 m
        else:
            geoms.append(wander(rng.randint(1, 200), 0.0005))
    # A closed loop inside the tolerance is what actually collapses: Douglas-
    # Peucker keeps its two endpoints, which are one point. 0.2 m across at
    # 1 m; 50 m across at 100 m.
    for size_deg in (0.000002, 0.0005):
        lon, lat = rng.uniform(-74.3, -73.9), rng.uniform(41.0, 41.4)
        loop = LineString([(lon, lat), (lon + size_deg, lat), (lon + size_deg, lat + size_deg), (lon, lat)])
        geoms.extend([loop, MultiLineString([wander(30, 0.0005), loop])])
    geoms.append(LineString([(-74.0, 41.0, 300.0), (-74.00001, 41.00001, 301.0), (-74.01, 41.01, 320.0)]))
    return geoms


@pytest.mark.parametrize("tolerance_m", [DEFAULT_SIMPLIFY_TOLERANCE_M, 100.0])
def test_batched_simplify_records_writes_what_the_per_record_loop_wrote(tolerance_m):
    records = [_record(geom, record_id=f"t{n}") for n, geom in enumerate(_awkward_lines(1661))]

    assert simplify_records(records, tolerance_m) == _simplify_one_record_at_a_time(records, tolerance_m)


def test_drawable_all_answers_what_has_drawable_geometry_answers():
    import numpy as np

    from export_trails import _drawable_all

    same_point = LineString([(-74.0, 41.0), (-74.0, 41.0)])
    geoms = [
        *_awkward_lines(7),
        same_point,
        LineString([(-74.0, 41.0), (-74.0, 41.0), (-74.0, 41.0)]),
        LineString([(0.0, 0.0), (-0.0, 0.0)]),  # a set says these are one point, and so does numpy
        MultiLineString([[(-74.0, 41.0), (-74.1, 41.1)], [(-74.2, 41.2), (-74.2, 41.2)]]),
        MultiLineString([[(-74.0, 41.0), (-74.1, 41.1)], [(-74.2, 41.2), (-74.3, 41.3)]]),
        LineString([(-74.0, 41.0, 1.0), (-74.0, 41.0, 2.0)]),  # distinct only in Z: the set counts two
    ]
    empties = [LineString(), MultiLineString()]

    answers = _drawable_all(np.array(geoms + empties, dtype=object)).tolist()

    assert answers[: len(geoms)] == [_has_drawable_geometry(geom) for geom in geoms]
    assert answers[len(geoms) :] == [False, False]
    assert not answers[geoms.index(same_point)]
