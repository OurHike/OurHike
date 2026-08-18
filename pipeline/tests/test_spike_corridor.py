"""Regression tests for the DuckDB spatial patterns used in spike_corridor.py.

spike_corridor.py itself is a script hardcoded to real file paths (data/raw/
centerline.geojson), not a library of importable functions - so these tests
exercise the same DuckDB SQL pattern directly against tiny synthetic
geometry, rather than calling the script. That's deliberate: the bug lives
in the ST_Transform/always_xy behavior itself, which any future script using
this pattern could reintroduce, not just this one file.
"""

import pytest

from tests.conftest import spatial_connection

PROJECTED_CRS = "EPSG:5070"
GEOGRAPHIC_CRS = "EPSG:4326"


@pytest.fixture
def con():
    return spatial_connection()


def test_transform_without_always_xy_produces_wrong_coordinates(con):
    """The bug as it actually manifested: EPSG:4326's authority-defined axis
    order is (lat, lon), but our data is (lon, lat). Without always_xy, GDAL/
    PROJ silently swaps the axes instead of erroring - on real (corridor-
    scale, 3,025-segment union) data this surfaced downstream as ST_Area
    returning nan, but that symptom depends on union complexity that isn't
    reliably reproducible in a small test. The root cause is directly
    testable though: a known point transforms to a wildly wrong location
    without always_xy - here, off by roughly 10x (a real, hardcoded fixed
    point, not a boundary of some tolerance), landing outside any plausible
    CONUS Albers coordinate range instead of the correct ~1.8M, 2.2M."""
    con.execute("CREATE TABLE t AS SELECT ST_GeomFromText('POINT(-74 41)') AS geom")
    x, y = con.execute(f"""
        SELECT ST_X(geom), ST_Y(geom) FROM (
            SELECT ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}') AS geom FROM t
        )
    """).fetchone()
    # Correct (always_xy) answer is ~(1819414, 2210531) - the buggy path
    # should be far outside a sane CONUS Albers range (roughly -2M to 3M).
    assert not (-2_000_000 < x < 3_000_000 and -2_000_000 < y < 3_000_000)


def test_transform_with_always_xy_roundtrips_correctly(con):
    """The fix: always_xy := true on both legs of the transform should
    round-trip a point back to (approximately) its original coordinates,
    with a sane, non-nan, non-zero corridor-scale area after buffering."""
    con.execute("CREATE TABLE t AS SELECT ST_GeomFromText('LINESTRING(-74 41, -73.9 41.1)') AS geom")

    buffer_meters = 30 * 1609.344
    con.execute(f"""
        CREATE TABLE corridor AS
        SELECT ST_Transform(
            ST_Buffer(
                ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true),
                {buffer_meters}
            ),
            '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true
        ) AS geom FROM t
    """)

    area_sq_mi = con.execute(f"""
        SELECT ST_Area(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true))
               / (1609.344 * 1609.344)
        FROM corridor
    """).fetchone()[0]

    assert area_sq_mi == area_sq_mi  # not nan
    assert area_sq_mi > 0
    # A 30-mile buffer around a ~9-mile line segment should be on the order of
    # a few thousand sq mi, not degenerate (~0) or absurd (~millions, which is
    # what the axis-swap bug produces by putting the geometry on the wrong
    # side of the globe before buffering).
    assert 1000 < area_sq_mi < 20000

    bbox = con.execute("SELECT ST_XMin(geom), ST_XMax(geom), ST_YMin(geom), ST_YMax(geom) FROM corridor").fetchone()
    xmin, xmax, ymin, ymax = bbox
    # Buffered bbox should still be in the neighborhood of the original point
    # (-74, 41), not wrapped to the wrong hemisphere/continent.
    assert -76 < xmin < -72
    assert -76 < xmax < -72
    assert 39 < ymin < 43
    assert 39 < ymax < 43


def test_clip_excludes_points_outside_corridor_and_includes_points_inside(con):
    """The clip step should demonstrably remove points outside the buffered
    corridor and keep points inside it - mirrors the real spike_corridor.py
    campsites/shelters clip, just on synthetic data."""
    con.execute("CREATE TABLE centerline AS SELECT ST_GeomFromText('LINESTRING(-74 41, -73.9 41.1)') AS geom")
    buffer_meters = 5 * 1609.344  # 5 miles - small buffer so "far" point is clearly outside
    con.execute(f"""
        CREATE TABLE corridor AS
        SELECT ST_Transform(
            ST_Buffer(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true), {buffer_meters}),
            '{PROJECTED_CRS}', '{GEOGRAPHIC_CRS}', always_xy := true
        ) AS geom FROM centerline
    """)

    con.execute("""
        CREATE TABLE pois AS
        SELECT * FROM (VALUES
            ('near', ST_GeomFromText('POINT(-73.95 41.05)')),
            ('far',  ST_GeomFromText('POINT(-70 38)'))
        ) AS t(name, geom)
    """)

    kept = con.execute("""
        SELECT p.name FROM pois p, corridor c WHERE ST_Intersects(p.geom, c.geom)
    """).fetchall()
    kept_names = {row[0] for row in kept}

    assert "near" in kept_names
    assert "far" not in kept_names
