"""The pure halves of spike_nyc_overlap.py (#1453) — the geometry helpers and
the overlap arithmetic, against tiny synthetic fixtures. The measurement half
runs against real fetched data and is not re-run here; these keep the
arithmetic honest so the numbers in the issue mean what they say."""

import math

import pytest

from spike_nyc_overlap import (
    METRES_PER_MILE,
    build_vertex_index,
    metres_between,
    near_index,
    overlap_report,
    segments,
)


def _line(coords, **props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}}


def _multiline(lines, **props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "MultiLineString", "coordinates": lines}}


# One degree of longitude at the spike's reference latitude, in metres - used
# to build fixtures whose separation in metres is known by construction.
def _east_of(point, metres):
    return [point[0] + metres / (111_320.0 * math.cos(math.radians(40.75))), point[1]]


def _north_of(point, metres):
    return [point[0], point[1] + metres / 110_570.0]


def test_segments_walks_both_geometry_shapes():
    assert segments(_line([[0, 0], [1, 1], [2, 2]])) == [([0, 0], [1, 1]), ([1, 1], [2, 2])]
    assert segments(_multiline([[[0, 0], [1, 1]], [[5, 5], [6, 6]]])) == [([0, 0], [1, 1]), ([5, 5], [6, 6])]


def test_segments_yields_nothing_for_an_empty_or_absent_geometry():
    """Nine of the greenway rows carry a geometry object with no coordinates,
    and the export drops them as `no geometry`. A spike that raised on those
    would be measuring its own fragility rather than the city's paths."""
    assert segments({"type": "Feature", "properties": {}, "geometry": None}) == []
    assert segments({"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": []}}) == []
    assert segments({"type": "Feature", "properties": {}}) == []


def test_metres_between_measures_a_constructed_separation():
    origin = [-73.97, 40.75]
    assert metres_between(origin, _east_of(origin, 100.0)) == pytest.approx(100.0, rel=1e-6)
    assert metres_between(origin, _north_of(origin, 250.0)) == pytest.approx(250.0, rel=1e-6)


def test_near_index_answers_on_the_radius_it_is_given():
    origin = [-73.97, 40.75]
    grid = build_vertex_index([_line([origin, _north_of(origin, 1.0)])])

    probe = _east_of(origin, 15.0)
    assert near_index(probe, grid, 25.0) is True
    assert near_index(probe, grid, 10.0) is False


def test_near_index_looks_beyond_its_own_grid_cell():
    """The radius can exceed the cell, so a vertex one cell over must still be
    found - getting this wrong would silently understate every overlap."""
    origin = [-73.97, 40.75]
    grid = build_vertex_index([_line([origin, _north_of(origin, 1.0)])], cell_m=10.0)

    assert near_index(_east_of(origin, 24.0), grid, 25.0, cell_m=10.0) is True


def test_overlap_report_counts_a_line_laid_along_the_index():
    """A greenway digitised alongside a parks trail is the case this exists to
    find: its whole length is within the radius, so all of it counts."""
    origin = [-73.97, 40.75]
    trail = _line([origin, _north_of(origin, 200.0)])
    grid = build_vertex_index([trail])

    alongside = _line([_east_of(origin, 5.0), _east_of(_north_of(origin, 200.0), 5.0)])
    report = overlap_report([alongside], grid, 25.0)

    assert report["shared_fraction"] > 0.99
    assert report["mostly_shared_features"] == 1
    assert report["total_mi"] == pytest.approx(200.0 / METRES_PER_MILE, rel=1e-3)


def test_overlap_report_ignores_a_line_that_merely_crosses():
    """BOTH endpoints of a piece must be near the index, so a path crossing a
    trail contributes nothing. Counting a crossing would turn every junction
    in a dense city into evidence of a double-draw."""
    origin = [-73.97, 40.75]
    grid = build_vertex_index([_line([origin, _north_of(origin, 2.0)])])

    # 400 m long, passing within a metre of the trail at its midpoint only.
    crossing = _line([_east_of(origin, -200.0), _east_of(origin, 200.0)])
    report = overlap_report([crossing], grid, 25.0)

    assert report["shared_mi"] == 0.0
    assert report["mostly_shared_features"] == 0


def test_overlap_report_groups_by_the_field_it_is_given():
    origin = [-73.97, 40.75]
    grid = build_vertex_index([_line([origin, _north_of(origin, 200.0)])])
    alongside = _line([_east_of(origin, 5.0), _east_of(_north_of(origin, 200.0), 5.0)], gwsystem="Fixture River")
    far = _line([_east_of(origin, 5000.0), _east_of(_north_of(origin, 200.0), 5000.0)], gwsystem="Fixture Bay")

    report = overlap_report([alongside, far], grid, 25.0, group_field="gwsystem")

    assert report["by_group"]["Fixture River"]["shared_mi"] > 0.1
    assert report["by_group"]["Fixture Bay"]["shared_mi"] == 0.0


def test_overlap_report_survives_a_set_with_no_length():
    """An all-empty input must report zero rather than dividing by it."""
    grid = build_vertex_index([_line([[-73.97, 40.75], [-73.97, 40.751]])])
    report = overlap_report([{"type": "Feature", "properties": {}, "geometry": None}], grid, 25.0)

    assert report["shared_fraction"] == 0.0
    assert report["total_mi"] == 0.0
