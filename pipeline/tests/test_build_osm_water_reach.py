"""Tests for build_osm_water_reach.py - #749's reachability gate on OSM water.

Synthetic geometry throughout (tests/synthetic.py's short Hudson Highlands
line), never the real corridor - see ../../TESTING.md. EPQS is stubbed rather
than mocked at the HTTP layer, because what these tests are about is which
verdict a given pair of elevations produces, not how the service is called.
"""

import json

import pytest

import build_osm_water_reach as reach
from tests.conftest import spatial_connection
from tests.synthetic import CENTERLINE_COORDS, write_centerline

# One degree of latitude in metres, for placing a point a known distance from
# the line's start. The gate binds at 30.5 m, so these offsets sit either side
# of it by enough that EPSG:5070's small distortion cannot flip a verdict.
M_PER_DEG_LAT = 111_132.0
JUST_INSIDE_DEG = 22.0 / M_PER_DEG_LAT
WELL_OUTSIDE_DEG = 60.0 / M_PER_DEG_LAT


def _write_fc(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _water(osm_id, lon, lat, kind="spring"):
    return {
        "type": "Feature",
        "properties": {"osm_id": str(osm_id), "kind": kind},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def _raw_dir(tmp_path, water_features):
    """A RAW_DIR holding every layer the gate reads.

    The side-trail, shelter and campsite layers are written EMPTY so each test
    below measures against the centerline alone - the union of three is its own
    test, and a test that meant to measure one distance should not be able to
    pass on a different one.
    """
    raw = tmp_path / "raw"
    raw.mkdir()
    write_centerline(raw / "centerline.geojson")
    _write_fc(raw / "side_trails.geojson", [])
    _write_fc(raw / "shelters.geojson", [])
    _write_fc(raw / "campsites.geojson", [])
    _write_fc(raw / "osm_water.geojson", water_features)
    return raw


def _measure(tmp_path, monkeypatch, water_features):
    monkeypatch.setattr(reach, "RAW_DIR", _raw_dir(tmp_path, water_features))
    con = spatial_connection()
    try:
        return {r["osm_id"]: r for r in reach.measure_distances(con, quiet=True)}
    finally:
        con.close()


# --- the distance gate ------------------------------------------------------


def test_a_point_on_the_trail_clears_the_distance_gate(tmp_path, monkeypatch):
    lon, lat = CENTERLINE_COORDS[0]
    records = _measure(tmp_path, monkeypatch, [_water(1, lon, lat)])
    assert records["1"]["passes_distance"] is True
    assert records["1"]["nearest"] == "centerline"
    assert records["1"]["nearest_m"] < 1.0


def test_a_point_just_inside_the_radius_clears_it_and_one_outside_does_not(tmp_path, monkeypatch):
    """The gate's own edge, from both sides. Placed south of the line's start,
    where the start endpoint is unambiguously the nearest point on it - a point
    offset beside the line could be nearest to some interior vertex instead, and
    then the test would be asserting against a distance it had not computed."""
    lon, lat = CENTERLINE_COORDS[0]
    records = _measure(
        tmp_path,
        monkeypatch,
        [_water(1, lon, lat - JUST_INSIDE_DEG), _water(2, lon, lat - WELL_OUTSIDE_DEG)],
    )
    assert records["1"]["passes_distance"] is True
    assert records["2"]["passes_distance"] is False
    assert "past the 100 ft a hiker walks for water" in records["2"]["reason"]


def test_a_point_with_nothing_within_the_ceiling_says_so(tmp_path, monkeypatch):
    """Not an error: the corridor is thirty miles wide, and 73.5% of its OSM
    water sits more than five miles from anything a hiker walks (2026-08-18).

    ~11 km south of the line's start: comfortably past MEASURE_CEILING_M (5 mi,
    8.05 km) and comfortably inside the 30-mile corridor, which clips before any
    of this runs. A point outside the corridor never reaches the measurement at
    all, and would test the clip rather than the ceiling."""
    lon, lat = CENTERLINE_COORDS[0]
    records = _measure(tmp_path, monkeypatch, [_water(1, lon, lat - 0.10)])
    assert records["1"]["passes_distance"] is False
    assert records["1"]["nearest"] is None
    assert records["1"]["nearest_m"] is None
    assert "no trail, side trail, shelter or campsite" in records["1"]["reason"]


def test_a_side_trail_can_win_the_union(tmp_path, monkeypatch):
    """The reason the gate is a union of three and not the centerline alone:
    72% of shelters sit past 90 ft from the centerline because they are at the
    end of a side trail, and OSM's water is there for the same reason."""
    lon, lat = CENTERLINE_COORDS[0]
    raw = _raw_dir(tmp_path, [_water(1, lon, lat - WELL_OUTSIDE_DEG)])
    # A side trail running south from the line's start, past the water point.
    _write_fc(
        raw / "side_trails.geojson",
        [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat], [lon, lat - WELL_OUTSIDE_DEG * 2]],
                },
            }
        ],
    )
    monkeypatch.setattr(reach, "RAW_DIR", raw)
    con = spatial_connection()
    try:
        records = {r["osm_id"]: r for r in reach.measure_distances(con, quiet=True)}
    finally:
        con.close()
    assert records["1"]["passes_distance"] is True
    assert records["1"]["nearest"] == "side_trail"


def test_a_shelter_can_win_the_union(tmp_path, monkeypatch):
    lon, lat = CENTERLINE_COORDS[0]
    raw = _raw_dir(tmp_path, [_water(1, lon, lat - WELL_OUTSIDE_DEG)])
    _write_fc(
        raw / "shelters.geojson",
        [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [lon, lat - WELL_OUTSIDE_DEG]},
            }
        ],
    )
    monkeypatch.setattr(reach, "RAW_DIR", raw)
    con = spatial_connection()
    try:
        records = {r["osm_id"]: r for r in reach.measure_distances(con, quiet=True)}
    finally:
        con.close()
    assert records["1"]["passes_distance"] is True
    assert records["1"]["nearest"] == "shelter"


# --- the grade gate ---------------------------------------------------------


def _distance_survivor(nearest_m=30.0):
    return {
        "osm_id": "1",
        "kind": "spring",
        "lon": -74.0,
        "lat": 41.0,
        "nearest": "centerline",
        "nearest_m": nearest_m,
        "walk_to": {"lon": -74.0, "lat": 41.0005},
        "passes_distance": True,
    }


def _stub_elevations(monkeypatch, water_ft, trail_ft):
    """elevation_ft keyed on latitude - the water point and the walk_to
    coordinate differ only in latitude in these fixtures."""
    monkeypatch.setattr(reach, "elevation_ft", lambda lat, lon: water_ft if lat == 41.0 else trail_ft)


def test_a_gentle_walk_clears_the_grade_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    # 5 ft over 98.4 ft of ground - a 5% grade, a path down a bank.
    _stub_elevations(monkeypatch, 1000.0, 1005.0)
    records = [_distance_survivor()]
    reach.apply_grade_gate(records, quiet=True)
    assert records[0]["passes_grade"] is True
    assert reach.is_reachable(records[0]) is True


def test_a_scramble_is_refused_and_says_why(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    # 50 ft over 98.4 ft - a 51% grade, which is the case the gate exists for.
    _stub_elevations(monkeypatch, 1000.0, 1050.0)
    records = [_distance_survivor()]
    reach.apply_grade_gate(records, quiet=True)
    assert records[0]["passes_grade"] is False
    assert "scramble rather than a walk" in records[0]["reason"]
    assert reach.is_reachable(records[0]) is False


def test_an_elevation_usgs_will_not_give_is_not_a_pass(tmp_path, monkeypatch):
    """An unknown is not a pass, and it is also not a rejection this file may
    blame on terrain - the reason has to say which of the two happened."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    monkeypatch.setattr(reach, "elevation_ft", lambda lat, lon: None)
    records = [_distance_survivor()]
    reach.apply_grade_gate(records, quiet=True)
    assert records[0]["passes_grade"] is False
    assert "would not give an elevation" in records[0]["reason"]
    assert reach.is_reachable(records[0]) is False


def test_a_point_that_failed_the_distance_gate_is_never_graded(tmp_path, monkeypatch):
    """EPQS answers in ~1.9 s, so grading the 1,430 points the distance gate
    already removed would cost an hour to learn nothing."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    monkeypatch.setattr(reach, "elevation_ft", lambda lat, lon: pytest.fail("should not be called"))
    records = [{"osm_id": "1", "passes_distance": False, "reason": "too far"}]
    reach.apply_grade_gate(records, quiet=True)
    assert "passes_grade" not in records[0]


def test_an_ungraded_survivor_is_not_reachable():
    """--limit leaves points graded next run; until then they are unknown, and
    an unknown may not publish as water."""
    assert reach.is_reachable(_distance_survivor()) is False


# --- the write guards -------------------------------------------------------


def _reachable_records(count):
    return [{"osm_id": str(i), "passes_distance": True, "passes_grade": True} for i in range(count)]


def test_write_stamps_the_verdict_onto_every_record(tmp_path, monkeypatch):
    """export_poi.py reads `reachable` and does no gate logic of its own, so a
    record that reached the file without it would publish as unreachable."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    records = _reachable_records(reach.MIN_REACHABLE) + [{"osm_id": "x", "passes_distance": False}]
    reach.write(records)
    payload = json.loads((tmp_path / "reach.json").read_text())
    verdicts = {r["osm_id"]: r["reachable"] for r in payload["points"]}
    assert verdicts["0"] is True
    assert verdicts["x"] is False
    assert payload["n_reachable"] == reach.MIN_REACHABLE


def test_write_refuses_a_collapsed_result(tmp_path, monkeypatch):
    """A run that read no trail geometry would otherwise publish "no water is
    reachable", which is false and is the one direction a water gate must never
    fail in."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    with pytest.raises(SystemExit, match="below the floor"):
        reach.write(_reachable_records(reach.MIN_REACHABLE - 1))


def test_write_refuses_a_halving_against_the_previous_run(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    with pytest.raises(SystemExit, match="drop guard"):
        reach.write(_reachable_records(reach.MIN_REACHABLE), previous=reach.MIN_REACHABLE * 10)


def test_the_drop_guard_compares_against_the_previous_run_not_this_ones_checkpoint(tmp_path, monkeypatch):
    """The regression this parameter exists for. apply_grade_gate checkpoints
    over OUT_PATH as it goes, so a guard that re-read the file at the end would
    be comparing the run against itself and could never fire."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    reach.write(_reachable_records(reach.MIN_REACHABLE * 10))
    previous = reach.read_previous_reachable_count()
    assert previous == reach.MIN_REACHABLE * 10

    # A mid-run checkpoint lands on the file, unguarded and small.
    reach.write(_reachable_records(reach.MIN_REACHABLE), guard=False)
    assert reach.read_previous_reachable_count() == reach.MIN_REACHABLE

    # The guarded write still fires, because the count was captured up front.
    with pytest.raises(SystemExit, match="drop guard"):
        reach.write(_reachable_records(reach.MIN_REACHABLE), previous=previous)
