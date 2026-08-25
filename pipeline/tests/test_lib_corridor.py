"""Tests for lib/corridor.py - the 30-mile AT corridor builder extracted out
of export_poi.py and export_trails.py (which used to each carry an
identical, verbatim-duplicated copy of this same function). Small synthetic
centerline fixture throughout (tiny GeoJSON built in test code), never the
real 3,025-segment centerline.geojson - see TESTING.md.
"""

import json

import pytest

from lib.corridor import NETWORK_BUFFER_FEET, build_corridor, count_features
from tests.conftest import spatial_connection
from tests.synthetic import CENTERLINE_COORDS, write_centerline


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


# --- the network widening (#1016) -------------------------------------------
#
# What this is for: until the corridor reached the ground under another
# organization's trail lines, every water point beside one was clipped away
# before any gate could look at it. build_osm_water_reach.py clips with this
# same table, so the corridor was the first of the three A.T.-shaped scopes and
# the one the other two sat behind.

# Far enough from CENTERLINE_COORDS to be outside its 30-mile buffer: one
# degree of latitude is ~69 miles, so this pair cannot be inside by accident.
NETWORK_COORDS = [(-74.0, 43.0), (-73.9, 43.1)]


def _network(path, coords=NETWORK_COORDS, features=None):
    if features is None:
        features = [
            {
                "type": "Feature",
                "properties": {"source": "oprhp_trails", "name": "A Park Trail"},
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
            }
        ]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def _contains(con, lon, lat) -> bool:
    return bool(con.execute(f"SELECT ST_Contains(geom, ST_Point({lon}, {lat})) FROM corridor").fetchone()[0])


def test_no_network_path_builds_the_corridor_it_always_built(tmp_path, con):
    """The A.T.-only call is unchanged, which is what lets export_trails.py go
    on passing one argument: its subject is ATC's own two layers and there is
    nothing of theirs outside this."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    assert build_corridor(con, centerline_path) is False
    assert _contains(con, *NETWORK_COORDS[0]) is False


def test_the_corridor_reaches_ground_only_a_network_line_touches(tmp_path, con):
    """#1016's defect, stated as a test: a point on somebody else's trail, well
    outside the A.T.'s thirty miles, that no water gate ever got to judge
    because the clip deleted it first."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")

    assert build_corridor(con, centerline_path, network_path) is True
    assert _contains(con, *NETWORK_COORDS[0]) is True


def test_the_widening_still_holds_the_at_corridor(tmp_path, con):
    """A union, not a replacement - the A.T.'s own thirty miles are still in
    there, and a widening that quietly lost them would delete every POI this
    export has ever published."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")

    build_corridor(con, centerline_path, network_path)

    assert _contains(con, *CENTERLINE_COORDS[0]) is True


def test_the_network_ring_is_narrow_rather_than_thirty_miles(tmp_path, con):
    """The asymmetry is the decision (NETWORK_BUFFER_FEET). The A.T.'s thirty
    miles are context - towns, resupply, parking - and NEARBY_TRAILS.md's
    decisions table gives the network none of that: amenity POIs stay
    chosen-trail-only, and only safety POIs are drawn for every trail. A mile
    out from a park trail is not this corridor's ground.
    """
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")

    build_corridor(con, centerline_path, network_path)

    lon, lat = NETWORK_COORDS[0]
    assert _contains(con, lon, lat - 1.0 / 69.0) is False


def test_the_ring_is_wider_than_the_gate_that_has_to_pass_through_it():
    """The relationship pinned rather than described. This clip must never be
    the thing that decides whether a safety POI reaches a hiker - that is the
    reach gate's job - so a re-tune of the gate's radius that outgrew the ring
    would silently start deleting points the gate had passed.
    """
    from build_osm_water_reach import MATCH_RADIUS_FT

    assert NETWORK_BUFFER_FEET > MATCH_RADIUS_FT


def test_an_empty_network_artifact_is_not_a_network(tmp_path, con):
    """The licence gate having held every steward's lines back. Not ground, and
    also the shape that makes ST_Read yield a table with no columns at all -
    see count_features."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    empty = _network(tmp_path / "nearby_trails.geojson", features=[])

    assert build_corridor(con, centerline_path, empty) is False


def test_a_missing_network_artifact_is_not_a_network(tmp_path, con):
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    assert build_corridor(con, centerline_path, tmp_path / "nowhere.geojson") is False


def test_count_features_survives_an_artifact_with_no_features(tmp_path, con):
    """The BinderException this exists to prevent: `ST_Read` infers columns
    from the features it finds, so every loader that names `source` or `geom`
    against an empty artifact raises rather than reading zero rows."""
    empty = _network(tmp_path / "nearby_trails.geojson", features=[])

    assert count_features(con, empty) == 0
    assert count_features(con, tmp_path / "nowhere.geojson") == 0
