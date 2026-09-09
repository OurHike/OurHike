"""Tests for check_water_reach.py - #916's re-derivation of #749's gate against
finished output rather than against a run's own belief about itself.

Synthetic geometry throughout (tests/synthetic.py's short Hudson Highlands
line), never the real corridor - see ../../TESTING.md. The offsets either side
of the gate are the ones test_build_osm_water_reach.py uses, and for its
reason: the gate binds at 30.5 m, so a test that meant to sit inside it must
not be close enough for EPSG:5070's small distortion to flip the verdict.
"""

import json

import check_water_reach as cwr
from tests.conftest import spatial_connection
from tests.synthetic import CENTERLINE_COORDS, write_centerline

M_PER_DEG_LAT = 111_132.0
JUST_INSIDE_DEG = 22.0 / M_PER_DEG_LAT
WELL_OUTSIDE_DEG = 60.0 / M_PER_DEG_LAT
# Past MEASURE_CEILING_M, so the distance is reported as "far" rather than as a
# number - the answer the 1,159 points past five miles all gave.
PAST_CEILING_DEG = 3000.0 / M_PER_DEG_LAT


def _write_fc(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _water(poi_id, lon, lat, source="osm_water"):
    return {
        "type": "Feature",
        "properties": {"id": poi_id, "poi_type": "water", "source": source},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def _point_layer(path, coords):
    _write_fc(
        path, [{"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": list(c)}} for c in coords]
    )


def _tree(tmp_path, water_features, *, shelters=(), campsites=(), side_trails=None, centerline=None):
    """A water layer plus the four layers the union is built from.

    The side-trail, shelter and campsite layers default to EMPTY so a test
    measuring against the centerline cannot accidentally pass on a different
    feature - the union of the four is its own test below.
    """
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    write_centerline(raw / "centerline.geojson", *([centerline] if centerline is not None else []))
    if side_trails is None:
        _write_fc(raw / "side_trails.geojson", [])
    else:
        _write_fc(raw / "side_trails.geojson", side_trails)
    _point_layer(raw / "shelters.geojson", shelters)
    _point_layer(raw / "campsites.geojson", campsites)

    water = tmp_path / "water.geojson"
    _write_fc(water, water_features)
    return water, [raw / "centerline.geojson", raw / "side_trails.geojson"], [raw / "shelters.geojson", raw / "campsites.geojson"]


def _check(tmp_path, water_features, **kwargs):
    tolerance_m = kwargs.pop("tolerance_m", 0.0)
    water, lines, sites = _tree(tmp_path, water_features, **kwargs)
    con = spatial_connection()
    try:
        return cwr.check_reach(water, lines, sites, tolerance_m=tolerance_m, con=con)
    finally:
        con.close()


# --- the gate itself --------------------------------------------------------


def test_a_point_on_the_trail_passes(tmp_path):
    lon, lat = CENTERLINE_COORDS[0]
    result = _check(tmp_path, [_water("osm_water:1", lon, lat)])
    assert result["problems"] == []
    assert result["checked"] == 1


def test_a_point_inside_the_gate_passes(tmp_path):
    lon, lat = CENTERLINE_COORDS[0]
    result = _check(tmp_path, [_water("osm_water:1", lon, lat + JUST_INSIDE_DEG)])
    assert result["problems"] == []


def test_a_point_outside_the_gate_is_reported_with_its_distance(tmp_path):
    lon, lat = CENTERLINE_COORDS[0]
    result = _check(tmp_path, [_water("osm_water:1", lon, lat + WELL_OUTSIDE_DEG)])
    assert len(result["past_gate"]) == 1
    # The distance is in the message, not just the verdict: a reader deciding
    # whether this is borderline or a fountain in a town park needs the figure.
    assert "osm_water:1" in result["problems"][0]
    assert "ft from the nearest" in result["problems"][0]


def test_the_failure_this_was_built_for_reports_a_distance_no_hiker_would_walk(tmp_path):
    """The live-bucket shape: a point so far out it is past the reporting
    ceiling, which is what 1,159 of the 1,535 published points were."""
    lon, lat = CENTERLINE_COORDS[0]
    result = _check(tmp_path, [_water("osm_water:1", lon, lat + PAST_CEILING_DEG)])
    assert len(result["past_gate"]) == 1
    assert result["past_gate"][0]["nearest_m"] is None
    assert result["worst"] == cwr.BEYOND_CEILING


# --- the union is four things -----------------------------------------------


def test_a_point_by_a_shelter_passes_though_the_centerline_is_far(tmp_path):
    """72% of shelters sit past 90 ft from the centerline, so a centerline-only
    check would flag OSM water for the reason side trails exist."""
    lon, lat = CENTERLINE_COORDS[0]
    shelter = (lon, lat + PAST_CEILING_DEG)
    result = _check(tmp_path, [_water("osm_water:1", *shelter)], shelters=[shelter])
    assert result["problems"] == []


def test_a_point_by_a_campsite_passes(tmp_path):
    lon, lat = CENTERLINE_COORDS[0]
    campsite = (lon, lat + PAST_CEILING_DEG)
    result = _check(tmp_path, [_water("osm_water:1", *campsite)], campsites=[campsite])
    assert result["problems"] == []


def test_a_point_by_a_side_trail_passes(tmp_path):
    lon, lat = CENTERLINE_COORDS[0]
    far_lat = lat + PAST_CEILING_DEG
    side = [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[lon, far_lat], [lon + 0.01, far_lat]]},
        }
    ]
    result = _check(tmp_path, [_water("osm_water:1", lon, far_lat)], side_trails=side)
    assert result["problems"] == []


# --- what it does and does not look at --------------------------------------


def test_only_osm_water_is_checked(tmp_path):
    """Every other water source arrives through a path with its own geography -
    see OSM_WATER_SOURCE. A far opentrail point is not this check's finding."""
    lon, lat = CENTERLINE_COORDS[0]
    far = lat + PAST_CEILING_DEG
    result = _check(
        tmp_path,
        [
            _water("opentrail_at:1", lon, far, source="opentrail_at"),
            _water("atc_csi:1", lon, far, source="atc_csi"),
            _water("nhd_stream:1", lon, far, source="nhd_stream"),
        ],
    )
    assert result["problems"] == []
    assert result["checked"] == 0


def test_a_water_layer_with_no_osm_points_passes_rather_than_skipping(tmp_path):
    """The normal state of every release before #529 added the source, and of
    any run that did not fetch it. A pass, because there is nothing wrong."""
    result = _check(tmp_path, [])
    assert result["problems"] == []
    assert result["checked"] == 0


def test_a_missing_water_layer_is_a_problem_the_caller_can_read(tmp_path):
    result = cwr.check_reach(tmp_path / "nope.geojson", [], [])
    assert result["problems"]
    assert "missing" in result["problems"][0]


def test_no_osm_points_and_no_layers_is_a_pass_rather_than_an_alarm(tmp_path):
    """The empty-union finding is about a check that measured wrongly, not
    about geometry a call never needed. With nothing to check, the layers being
    absent is not a defect - a run that exported no OSM water and fetched no
    trail layers has nothing here to be wrong about."""
    water = tmp_path / "water.geojson"
    _write_fc(water, [])

    result = cwr.check_reach(water, [tmp_path / "absent.geojson"], [])

    assert result["problems"] == []
    assert result["checked"] == 0


def test_measuring_against_no_geometry_at_all_is_the_finding(tmp_path):
    """The direction that matters: an empty union would pass every point,
    which is the opposite of the truth rather than a lenient version of it."""
    lon, lat = CENTERLINE_COORDS[0]
    water = tmp_path / "water.geojson"
    _write_fc(water, [_water("osm_water:1", lon, lat + PAST_CEILING_DEG)])
    result = cwr.check_reach(water, [tmp_path / "absent.geojson"], [])
    assert result["problems"]
    assert "measured against nothing" in result["problems"][0]
    # And it must not be reported as if the points had been measured and passed.
    assert result["past_gate"] == []


# --- the tolerance ----------------------------------------------------------


def test_the_tolerance_is_what_widens_the_gate_and_nothing_else_does(tmp_path):
    """A caller measuring against simplified geometry passes the bound that
    simplification guarantees, and the same point either side of that bound
    has to get opposite verdicts.

    Its own centerline, and the margins are 10 m rather than the metre
    `DEFAULT_SIMPLIFY_TOLERANCE_M` actually is. Both are limits of the fixture
    rather than of the check, and both are worth stating because a reader will
    otherwise assume this test is tighter than it is:

    - CENTERLINE_COORDS runs diagonally, so a point offset north of it sits
      only ~0.6x that far from the line. This test is the one whose subject IS
      the distance, so it uses a constant-latitude line, where a latitude
      offset is very nearly the perpendicular distance.
    - "Very nearly" is ~2.3% at this latitude, EPSG:5070's own scale factor. A
      one-metre assertion would be asserting that distortion rather than the
      gate, which is the same reason the tests above sit 22 m or 60 m from the
      line rather than 30.
    """
    lon, lat = -74.0, 41.0
    horizontal = [(lon, lat), (lon + 0.1, lat)]
    past_gate = (cwr.MATCH_RADIUS_M + 10.0) / M_PER_DEG_LAT
    point = [_water("osm_water:1", lon + 0.05, lat + past_gate)]
    assert len(_check(tmp_path, point, centerline=horizontal)["past_gate"]) == 1
    assert _check(tmp_path, point, centerline=horizontal, tolerance_m=20.0)["problems"] == []


# --- the report a reader gets -----------------------------------------------


def test_a_long_list_of_offenders_is_capped_but_the_count_is_not(tmp_path):
    """1,412 problems is not a report. The count stays exact."""
    lon, lat = CENTERLINE_COORDS[0]
    points = [_water(f"osm_water:{i}", lon + i * 0.0001, lat + PAST_CEILING_DEG) for i in range(cwr.MAX_NAMED + 5)]
    result = _check(tmp_path, points)
    assert len(result["past_gate"]) == cwr.MAX_NAMED + 5
    assert len(result["problems"]) == cwr.MAX_NAMED + 1
    assert "and 5 more" in result["problems"][-1]


def test_the_worst_offender_is_named_first(tmp_path):
    lon, lat = CENTERLINE_COORDS[0]
    result = _check(
        tmp_path,
        [
            _water("osm_water:near", lon, lat + WELL_OUTSIDE_DEG),
            _water("osm_water:far", lon, lat + PAST_CEILING_DEG),
        ],
    )
    assert result["past_gate"][0]["id"] == "osm_water:far"
    assert "osm_water:far" in result["problems"][0]


def test_the_gate_is_fetch_trail_waters_and_not_a_second_copy_of_it():
    """A checker that could disagree with the gate would be a second opinion.
    Both numbers come from the one module that decides them."""
    from fetch_trail_water import M_PER_FT, MATCH_RADIUS_FT

    assert cwr.MATCH_RADIUS_FT is MATCH_RADIUS_FT
    assert cwr.MATCH_RADIUS_M == MATCH_RADIUS_FT * M_PER_FT


# --- the union this checks has to be the gate's union (#1016) ---------------


def test_the_network_lines_join_the_lines_this_measures_against(tmp_path, monkeypatch):
    """A checker measuring against a narrower union than the gate would fail
    every point the gate correctly passed on a network trail - and "the release
    gate went red on water" is exactly the kind of noise that gets a check
    switched off rather than believed."""
    processed = tmp_path / "processed"
    (processed / "poi").mkdir(parents=True)
    network = processed / "nearby_trails.geojson"
    network.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    monkeypatch.setattr(cwr, "PROCESSED_DIR", processed)

    _, lines, _ = cwr.processed_paths()

    assert network in lines


def test_an_at_only_publish_checks_what_it_always_checked(tmp_path, monkeypatch):
    """No network artifact is the ordinary state on a publish whose licences
    are held back, and it must not change what this measures."""
    processed = tmp_path / "processed"
    (processed / "poi").mkdir(parents=True)
    monkeypatch.setattr(cwr, "PROCESSED_DIR", processed)

    _, lines, _ = cwr.processed_paths()

    assert [path.name for path in lines] == ["centerline.geojson", "side_trails.geojson"]
