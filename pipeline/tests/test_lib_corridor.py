"""Tests for lib/corridor.py - the 30-mile AT corridor builder extracted out
of export_poi.py and export_trails.py (which used to each carry an
identical, verbatim-duplicated copy of this same function). Small synthetic
centerline fixture throughout (tiny GeoJSON built in test code), never the
real 3,025-segment centerline.geojson - see TESTING.md.
"""

import json

import pytest

from lib.corridor import NETWORK_BUFFER_FEET, NETWORK_TABLE, build_corridor, count_features, keep_within_corridor
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
    """Whether the `corridor` POLYGON contains the point - the A.T.'s own
    thirty miles, and since #1311 nothing else."""
    return bool(con.execute(f"SELECT ST_Contains(geom, ST_Point({lon}, {lat})) FROM corridor").fetchone()[0])


def _reaches(con, lon, lat) -> bool:
    """Whether the corridor as a whole reaches the point - the polygon or the
    network ring - which is the question every clip asks."""
    con.execute("CREATE OR REPLACE TABLE probe (id INTEGER, lon DOUBLE, lat DOUBLE)")
    con.execute("INSERT INTO probe VALUES (1, ?, ?)", [lon, lat])
    return keep_within_corridor(con, "probe", "id", "lon", "lat") == 1


def test_no_network_path_builds_the_corridor_it_always_built(tmp_path, con):
    """The A.T.-only call is unchanged, which is what lets export_trails.py go
    on passing one argument: its subject is ATC's own two layers and there is
    nothing of theirs outside this."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)

    assert build_corridor(con, centerline_path) is False
    assert _contains(con, *NETWORK_COORDS[0]) is False
    assert _reaches(con, *NETWORK_COORDS[0]) is False


def test_the_corridor_reaches_ground_only_a_network_line_touches(tmp_path, con):
    """#1016's defect, stated as a test: a point on somebody else's trail, well
    outside the A.T.'s thirty miles, that no water gate ever got to judge
    because the clip deleted it first."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")

    assert build_corridor(con, centerline_path, network_path) is True
    assert _reaches(con, *NETWORK_COORDS[0]) is True


def test_the_widening_still_holds_the_at_corridor(tmp_path, con):
    """A union, not a replacement - the A.T.'s own thirty miles are still in
    there, and a widening that quietly lost them would delete every POI this
    export has ever published."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")

    build_corridor(con, centerline_path, network_path)

    assert _contains(con, *CENTERLINE_COORDS[0]) is True
    assert _reaches(con, *CENTERLINE_COORDS[0]) is True


def test_the_polygon_stays_the_at_s_and_the_ring_is_a_join(tmp_path, con):
    """#1311's decision, pinned. The network is not unioned into the
    `corridor` polygon any more - 112,439 buffered lines made that a
    20-minute ST_Union_Agg paid twice per build - it is an R-tree-indexed
    line table beside it, and only `keep_within_corridor` reaches both. A
    caller reading the polygon directly gets the A.T.'s ground, which is
    what every such caller wants."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")

    build_corridor(con, centerline_path, network_path)

    assert _contains(con, *NETWORK_COORDS[0]) is False
    assert _reaches(con, *NETWORK_COORDS[0]) is True
    assert con.execute(f"SELECT count(*) FROM {NETWORK_TABLE}").fetchone()[0] == 1


def test_the_ring_keeps_a_point_inside_it_and_drops_one_just_past_it(tmp_path, con):
    """The join answers the same set the union did: a point within
    NETWORK_BUFFER_FEET of a line is kept, one past it is not. Offsets are
    due south of the line's first vertex, where the nearest point on the
    line IS that vertex, so the distance is the offset itself
    (one degree of latitude is ~111 km)."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")
    build_corridor(con, centerline_path, network_path)

    lon, lat = NETWORK_COORDS[0]
    inside_ft, outside_ft = NETWORK_BUFFER_FEET * 0.8, NETWORK_BUFFER_FEET * 1.2
    degrees_per_foot = 0.3048 / 111_000

    assert _reaches(con, lon, lat - inside_ft * degrees_per_foot) is True
    assert _reaches(con, lon, lat - outside_ft * degrees_per_foot) is False


def test_keep_within_corridor_answers_many_rows_at_once_with_their_own_ids(tmp_path, con):
    """The shape both clips use: a table of candidates in, `corridor_hits`
    out, ids untouched - a string id stays a string, which is what lets
    build_osm_water_reach.py join it straight back to its rows."""
    centerline_path = tmp_path / "centerline.geojson"
    write_centerline(centerline_path)
    network_path = _network(tmp_path / "nearby_trails.geojson")
    build_corridor(con, centerline_path, network_path)

    con.execute("CREATE TABLE candidates (osm_id VARCHAR, lon DOUBLE, lat DOUBLE)")
    con.executemany(
        "INSERT INTO candidates VALUES (?, ?, ?)",
        [
            ("on_the_at", *CENTERLINE_COORDS[0]),
            ("on_a_park_trail", *NETWORK_COORDS[0]),
            ("a_mile_off_the_park_trail", NETWORK_COORDS[0][0], NETWORK_COORDS[0][1] - 1.0 / 69.0),
            ("nowhere_near", -70.0, 38.0),
        ],
    )

    assert keep_within_corridor(con, "candidates", "osm_id", "lon", "lat") == 2
    kept = {row[0] for row in con.execute("SELECT id FROM corridor_hits ORDER BY id").fetchall()}
    assert kept == {"on_the_at", "on_a_park_trail"}


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
    assert _reaches(con, lon, lat - 1.0 / 69.0) is False


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
