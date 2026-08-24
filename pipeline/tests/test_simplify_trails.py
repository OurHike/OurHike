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
