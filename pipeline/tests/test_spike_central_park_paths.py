"""The pure halves of spike_central_park_paths.py (#1530) - the clipping, the
"is this path we already draw" subtraction, and the area-to-centerline band,
against boxes and lines small enough to check by hand.

The measurement half runs against real fetched data and is not re-run here.
These exist so the figures in #1530 mean what they say: a park that draws 34%
of the city's line data where its neighbour draws 96% is a claim resting on
this arithmetic, and the arithmetic is worth a fixture.

Everything here works in FLAT METRES, which is the whole reason the spike's
helpers take projected geometries - a test can build a 1,000 m park out of a
box and know the answers without a projection, a fetch or a coordinate.
"""

import pytest
from shapely.geometry import LineString, Polygon, box

from spike_central_park_paths import (
    METRES_PER_MILE,
    acres,
    clip,
    implied_centerline_miles,
    length_beyond,
    miles,
    to_metres,
    total_length,
)

#: A 1,000 m square "park" at the origin. Every expectation below is arithmetic
#: against this box.
PARK = box(0, 0, 1000, 1000)


def _feature(coordinates, geometry_type="LineString", **properties):
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": geometry_type, "coordinates": coordinates},
    }


def test_miles_and_acres_convert_against_their_own_constants():
    assert miles(METRES_PER_MILE) == pytest.approx(1.0)
    assert acres(4046.8564224) == pytest.approx(1.0)


def test_clip_keeps_only_the_part_of_a_line_inside_the_boundary():
    """A path running out of the park counts for the half that is in it. The
    Central Park figure is a per-acre density, so a line leaving the boundary
    and counting whole would inflate exactly the number the finding rests on."""
    crossing = LineString([(500, 500), (500, 2000)])
    kept = clip([crossing], PARK)
    assert total_length(kept) == pytest.approx(500.0)


def test_clip_drops_a_geometry_that_misses_the_boundary_entirely():
    outside = LineString([(5000, 5000), (6000, 5000)])
    assert clip([outside], PARK) == []


def test_clip_handles_a_line_wholly_inside():
    inside = LineString([(100, 100), (400, 100)])
    assert total_length(clip([inside], PARK)) == pytest.approx(300.0)


def test_length_beyond_subtracts_a_reference_line_running_alongside():
    """Two agencies digitising one tread never share a vertex, so "already
    drawn" is a question about proximity. A path 10 m from a drawn line is the
    same path; the 25 m radius the spike uses says so deliberately."""
    drawn = LineString([(0, 500), (1000, 500)])
    same_tread = LineString([(0, 510), (1000, 510)])
    assert length_beyond([same_tread], [drawn], 25.0) == pytest.approx(0.0)


def test_length_beyond_keeps_a_path_further_off_than_the_radius():
    drawn = LineString([(0, 500), (1000, 500)])
    elsewhere = LineString([(0, 900), (1000, 900)])
    assert length_beyond([elsewhere], [drawn], 25.0) == pytest.approx(1000.0, rel=1e-3)


def test_length_beyond_splits_a_path_that_is_half_alongside():
    """The measurement that carries #1530's "97% is path we do not have": a
    half-covered line must contribute its other half, not all or nothing."""
    drawn = LineString([(0, 500), (500, 500)])
    half_alongside = LineString([(0, 505), (1000, 505)])
    assert length_beyond([half_alongside], [drawn], 25.0) == pytest.approx(500.0, abs=30.0)


def test_length_beyond_with_no_reference_returns_the_whole_length():
    """Not an edge case - it is the answer for a park where nothing is drawn,
    and returning 0.0 there would report perfect coverage of an empty map."""
    path = LineString([(0, 0), (300, 0)])
    assert length_beyond([path], [], 25.0) == pytest.approx(300.0)


def test_implied_centerline_miles_returns_the_band_smallest_first():
    """A WIDER assumed walkway implies LESS centerline, so the band inverts on
    its way through. Returning it smallest-first is what stops a reader
    comparing the wrong end against a published mileage."""
    area = 30_000.0
    low, high = implied_centerline_miles(area, (3.0, 5.0))
    assert low < high
    assert low == pytest.approx(miles(area / 5.0))
    assert high == pytest.approx(miles(area / 3.0))


def test_implied_centerline_miles_does_not_care_which_way_the_band_is_written():
    assert implied_centerline_miles(30_000.0, (5.0, 3.0)) == implied_centerline_miles(30_000.0, (3.0, 5.0))


def test_to_metres_skips_a_feature_with_no_geometry_or_no_coordinates():
    """Nine rows of the greenway layer carry a geometry object with an empty
    coordinate list, and the exporter drops them as `no geometry`. A spike that
    raised on those would be measuring its own fragility."""
    features = [
        {"type": "Feature", "properties": {}, "geometry": None},
        {"type": "Feature", "properties": {}},
        _feature([]),
        _feature([[-73.97, 40.78], [-73.96, 40.78]]),
    ]
    assert len(to_metres(features)) == 1


def test_to_metres_projects_into_something_measurable_in_metres():
    """One tenth of a degree of latitude is ~11.1 km on the ground, and UTM 18N
    is where the spike's distances live. This is the projection working, not
    its precision - within 1% is all the finding needs."""
    line = _feature([[-73.97, 40.70], [-73.97, 40.80]])
    (projected,) = to_metres(line and [line])
    assert projected.length == pytest.approx(11_100.0, rel=0.01)


def test_to_metres_reads_a_multilinestring_as_one_geometry():
    multi = _feature([[[-73.97, 40.78], [-73.96, 40.78]], [[-73.95, 40.78], [-73.94, 40.78]]], "MultiLineString")
    (projected,) = to_metres([multi])
    assert projected.geom_type == "MultiLineString"
    assert projected.length > 0


def test_a_park_polygon_clips_an_area_the_way_it_clips_a_line():
    """The walkway figure is an AREA through the same clip(), so it gets the
    same test: a polygon half in the park contributes half its surface."""
    walkway = Polygon([(900, 0), (1100, 0), (1100, 100), (900, 100)])
    (kept,) = clip([walkway], PARK)
    assert kept.area == pytest.approx(10_000.0)
