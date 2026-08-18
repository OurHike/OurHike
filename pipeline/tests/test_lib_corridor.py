"""Tests for lib/corridor.py - the 30-mile AT corridor builder extracted out
of export_poi.py and export_trails.py (which used to each carry an
identical, verbatim-duplicated copy of this same function). Small synthetic
centerline fixture throughout (tiny GeoJSON built in test code), never the
real 3,025-segment centerline.geojson - see TESTING.md.
"""

import pytest

from lib.corridor import build_corridor
from tests.conftest import spatial_connection
from tests.synthetic import write_centerline


@pytest.fixture
def con():
    return spatial_connection()


def test_build_corridor_populates_a_single_non_empty_polygon(tmp_path, con):
    """The 'corridor' table should exist with exactly one row and a real,
    non-empty geometry after build_corridor runs - the basic postcondition
    every caller (export_poi.py's/export_trails.py's clip_to_corridor)
    relies on."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    build_corridor(con, centerline_path)

    row_count = con.execute("SELECT COUNT(*) FROM corridor").fetchone()[0]
    assert row_count == 1

    is_empty = con.execute("SELECT ST_IsEmpty(geom) FROM corridor").fetchone()[0]
    assert is_empty is False


def test_build_corridor_area_is_plausible_for_a_30_mile_buffer_around_the_fixture_line(tmp_path, con):
    """A 30-mile buffer around this ~9-mile fixture line should be on the
    order of a few thousand sq mi - the same plausible-range reasoning
    test_spike_corridor.py's test_transform_with_always_xy_roundtrips_correctly
    uses for the identical coordinates, not degenerate (~0, e.g. an empty or
    collapsed geometry) or absurd (~millions, what an axis-swapped transform
    produces by putting the geometry on the wrong side of the globe before
    buffering)."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    build_corridor(con, centerline_path)

    area_sq_mi = con.execute("""
        SELECT ST_Area(ST_Transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true))
               / (1609.344 * 1609.344)
        FROM corridor
    """).fetchone()[0]

    assert area_sq_mi == area_sq_mi  # not nan
    assert 1000 < area_sq_mi < 20000


def test_build_corridor_keeps_the_result_in_the_source_hemisphere_not_axis_swapped(tmp_path, con):
    """Regression guard for the always_xy gotcha (README.md's "Gotcha hit and
    fixed" note): EPSG:4326's authority-defined axis order is (lat, lon), but
    the fixture (and every real geometry source this pipeline reads) is
    (lon, lat). If a future edit dropped always_xy := true from either
    ST_Transform leg, the corridor would come back transformed as if every
    point were on the wrong side of the globe - so its bbox is asserted to
    stay in the fixture's own quadrant (western hemisphere, negative
    longitude; northern hemisphere, positive latitude, close to the original
    (-74, 41) point), not swapped or wrapped somewhere nonsensical."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    build_corridor(con, centerline_path)

    xmin, xmax, ymin, ymax = con.execute(
        "SELECT ST_XMin(geom), ST_XMax(geom), ST_YMin(geom), ST_YMax(geom) FROM corridor"
    ).fetchone()

    # Same sane-neighborhood bounds test_spike_corridor.py's own always_xy
    # regression test asserts for this coordinate pair's 30-mile buffer.
    assert -76 < xmin < -72
    assert -76 < xmax < -72
    assert 39 < ymin < 43
    assert 39 < ymax < 43
