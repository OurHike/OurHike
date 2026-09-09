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


def _measure(tmp_path, monkeypatch, water_features, network_features=None, shipped=None):
    """Measure against a synthetic RAW_DIR, and against network lines only when
    a test asks for them.

    NETWORK_LINES_PATH is redirected in every case, including the default one
    (#1016). It is a real path under data/processed/ and would otherwise be
    whatever the machine happens to have on disk - so a developer with a
    fetched tree would be measuring 3,663 real lines against a synthetic
    corridor, and these tests would say different things on different machines.
    Pointing it at a file that does not exist is the A.T.-only case stated
    rather than assumed.
    """
    monkeypatch.setattr(reach, "RAW_DIR", _raw_dir(tmp_path, water_features))
    # Which organizations count is the registry's answer in production, and a
    # test's own here - otherwise these read the real sources.json and would
    # start or stop passing when somebody's licence answer lands.
    if shipped is None:
        shipped = {feature["properties"]["source"] for feature in network_features or []}
    monkeypatch.setattr(reach, "shipped_network_keys", lambda: shipped)
    network_path = tmp_path / "nearby_trails.geojson"
    if network_features is not None:
        _write_fc(network_path, network_features)
    monkeypatch.setattr(reach, "NETWORK_LINES_PATH", network_path)
    con = spatial_connection()
    try:
        return {r["osm_id"]: r for r in reach.measure_distances(con, quiet=True)}
    finally:
        con.close()


def _network_line(coords, source="oprhp_trails", name="Appalachian Approach"):
    return {
        "type": "Feature",
        "properties": {"source": source, "name": name, "blaze_color": "blue"},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
    }


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
    assert "no trail, side trail, network trail, shelter or campsite" in records["1"]["reason"]


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


# --- the short-run floor (#815) ---------------------------------------------
#
# Runs are given in metres because that is what `nearest_m` holds, and chosen to
# land either side of MIN_GRADE_RUN_FT rather than on it: 3.048 m divides to
# 10.0 ft only up to float representation, and a test that turns on that is
# testing the division rather than the gate.


def test_a_spring_at_the_trailside_is_not_a_scramble(tmp_path, monkeypatch):
    """#815's node 553354783, in miniature: a spring 0.26 m from the side trail
    it sits beside, 0.4 ft of drop, refused as "a 39% grade, which is a scramble
    rather than a walk". It is a spring ON the trail, and springs are the class
    this source exists to cover."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    _stub_elevations(monkeypatch, 1000.0, 1000.4)
    records = [_distance_survivor(nearest_m=0.26)]

    reach.apply_grade_gate(records, quiet=True)

    assert records[0]["passes_grade"] is True
    assert reach.is_reachable(records[0]) is True
    assert "reason" not in records[0]
    # The ratio still reads as a scramble - the verdict stopped believing it,
    # and the file keeps the number either way so the floor can be re-argued.
    assert records[0]["grade"] > reach.MAX_GRADE
    assert records[0]["grade_floored"] is True


def test_a_run_just_under_the_floor_is_not_graded(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    # 5 ft of drop over 9.5 ft of run - a 53% ratio, and still not a walk this
    # file will call a scramble.
    _stub_elevations(monkeypatch, 1000.0, 1005.0)
    records = [_distance_survivor(nearest_m=2.9)]

    reach.apply_grade_gate(records, quiet=True)

    assert records[0]["passes_grade"] is True
    assert records[0]["grade_floored"] is True


def test_the_floor_does_not_rescue_a_real_bank(tmp_path, monkeypatch):
    """The regression this floor could have introduced. 10.2 ft of run is over
    the floor, so the ratio is believed again - #815 measured the other ~49
    refusals at a median 0.24 over 10-100 ft runs, and every one of them has to
    still be refused after this change."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    _stub_elevations(monkeypatch, 1000.0, 1005.0)
    records = [_distance_survivor(nearest_m=3.1)]

    reach.apply_grade_gate(records, quiet=True)

    assert records[0]["passes_grade"] is False
    assert "scramble rather than a walk" in records[0]["reason"]
    assert "grade_floored" not in records[0]
    assert reach.is_reachable(records[0]) is False


def test_a_short_gentle_walk_is_not_marked_as_floored(tmp_path, monkeypatch):
    """The marker means "the floor changed this verdict", not "the run was
    short" - a point that would have passed on its grade anyway is not one of
    the ones #815 leaves open to counting."""
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")
    # 1 ft over 9.5 ft is a 10% grade, under MAX_GRADE on its own merits.
    _stub_elevations(monkeypatch, 1000.0, 1001.0)
    records = [_distance_survivor(nearest_m=2.9)]

    reach.apply_grade_gate(records, quiet=True)

    assert records[0]["passes_grade"] is True
    assert "grade_floored" not in records[0]


# --- re-grading a file written under a different floor (#815) ---------------


def _graded(osm_id="1", nearest_m=30.0, passes=False):
    record = _distance_survivor(nearest_m=nearest_m)
    record["osm_id"] = osm_id
    record["passes_grade"] = passes
    record["grade"] = 0.4
    record["drop_ft"] = 4.0
    if not passes:
        record["reason"] = "the ground drops 4 ft over 10 ft - a 40% grade"
    return record


def test_a_short_walk_graded_under_no_floor_is_re_graded():
    """The path that decides whether this fix reaches anybody. apply_grade_gate
    skips records that already carry a verdict, and the publish workflow
    restores data/raw/ from the Actions cache (#812) - so without this, a
    changed floor never touches the file on disk."""
    records = [_graded(nearest_m=0.26)]

    cleared = reach.drop_stale_grade_verdicts(records, None)

    assert cleared == 1
    assert "passes_grade" not in records[0]
    assert "reason" not in records[0]


def test_a_longer_walk_keeps_its_verdict_and_its_lookups():
    """A floor cannot change a walk longer than itself, and re-grading one
    costs two EPQS calls to arrive at the same answer."""
    records = [_graded(nearest_m=30.0)]

    cleared = reach.drop_stale_grade_verdicts(records, None)

    assert cleared == 0
    assert records[0]["passes_grade"] is False


def test_a_file_written_under_this_floor_is_left_alone():
    records = [_graded(nearest_m=0.26)]

    cleared = reach.drop_stale_grade_verdicts(records, reach.MIN_GRADE_RUN_FT)

    assert cleared == 0
    assert records[0]["passes_grade"] is False


def test_lowering_the_floor_re_grades_what_the_old_one_had_rescued():
    """The other direction: a verdict taken under a WIDER floor is just as stale
    as one taken under none, and the points it rescued have to be re-asked."""
    records = [_graded(nearest_m=6.0, passes=True)]  # 19.7 ft - past today's floor
    records[0]["grade_floored"] = True

    cleared = reach.drop_stale_grade_verdicts(records, 25.0)

    assert cleared == 1
    assert "passes_grade" not in records[0]
    assert "grade_floored" not in records[0]


def test_a_point_that_never_reached_the_grade_gate_is_untouched():
    """Distance failures carry a reason too, and it is not this function's to
    clear - they were never graded."""
    records = [{"osm_id": "1", "passes_distance": False, "reason": "too far"}]

    cleared = reach.drop_stale_grade_verdicts(records, None)

    assert cleared == 0
    assert records[0]["reason"] == "too far"


def test_main_re_grades_a_stale_file_it_resumes_from(tmp_path, monkeypatch):
    """End to end on the path that actually runs in CI: a file the Actions cache
    restored, written before the floor existed, resumed rather than remeasured.
    The unit test above proves the clearing; this proves main() calls it, which
    is the half that would fail silently by producing the old verdicts."""
    out = tmp_path / "reach.json"
    monkeypatch.setattr(reach, "OUT_PATH", out)
    # NETWORK_LINES_PATH for the same reason `_measure` redirects it, and this
    # is the one test that reaches main() without going through that helper
    # (#1139). Resuming is the whole subject here, and `wants_remeasure` asks
    # whether the artifact exists: on a tree that has run export_nearby_trails.py
    # the real file is there, the stale payload carries no
    # `measured_against_network` key, and main() re-measures instead - reaching
    # for a data/raw/centerline.geojson no test ever staged. Absent is the
    # resume case stated rather than left to whatever the machine has on disk.
    monkeypatch.setattr(reach, "NETWORK_LINES_PATH", tmp_path / "nearby_trails.geojson")
    monkeypatch.setattr(reach.fetch_receipts, "record", lambda *a, **k: {})
    _stub_elevations(monkeypatch, 1000.0, 1000.4)  # 0.4 ft drop
    stale = [_graded(osm_id=str(i), nearest_m=0.26) for i in range(reach.MIN_REACHABLE + 5)]
    # No `min_grade_run_ft` key: this is a pre-#815 file.
    out.write_text(json.dumps({"n_reachable": 0, "points": stale}), encoding="utf-8")

    assert reach.main([]) == 0

    written = json.loads(out.read_text())
    assert written["min_grade_run_ft"] == reach.MIN_GRADE_RUN_FT
    assert written["n_reachable"] == len(stale)
    assert all(p["grade_floored"] for p in written["points"])


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
    """The regression the `previous` parameter exists for.

    Checkpoints no longer land on OUT_PATH - they go to CHECKPOINT_PATH - so a
    guard that re-read the file would now get the right answer. The parameter
    stays anyway, and this test with it: a guard that reads its own baseline
    out of the file it is about to overwrite is the shape that failed, and it
    is not worth rebuilding on the argument that nothing else writes there now.
    This case still passes an unguarded write straight at OUT_PATH to prove the
    parameter, not the paths.
    """
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


def test_a_checkpoint_does_not_touch_the_finished_file(tmp_path, monkeypatch):
    """The guard can only protect a file nothing else writes.

    apply_grade_gate checkpointed to OUT_PATH every 25 points and once more at
    the end, all with guard=False - so by the time the guarded write refused a
    collapsed result, the collapse was already the file on disk, and
    export_poi.py's next read would take it.
    """
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")

    good = reach.MIN_REACHABLE * 10
    reach.write(_reachable_records(good))

    reach.write(_reachable_records(1), guard=False, path=reach.checkpoint_path())

    assert json.loads((tmp_path / "reach.json").read_text())["n_reachable"] == good
    assert reach.checkpoint_path().exists()


def test_a_failed_guard_leaves_the_baseline_the_next_run_reads(tmp_path, monkeypatch):
    """The second half, and the worse half: a collapse used to launder itself.

    `previous` comes from OUT_PATH. While checkpoints wrote there too, a
    collapsed run left its own count behind - so the NEXT run compared the
    collapse against itself and sailed through a guard the first run had just
    failed (45 against a "previous" of 45 passes a 50% drop that 45 against 900
    does not). A total collapse was worse again: `previous` became 0, and
    `if previous and ...` is false for 0, so the drop guard switched itself off
    and only MIN_REACHABLE was left standing.
    """
    monkeypatch.setattr(reach, "OUT_PATH", tmp_path / "reach.json")

    good = reach.MIN_REACHABLE * 10
    reach.write(_reachable_records(good))

    # A run collapses: checkpoints land, then the guarded write refuses.
    reach.write(_reachable_records(reach.MIN_REACHABLE), guard=False, path=reach.checkpoint_path())
    with pytest.raises(SystemExit, match="drop guard"):
        reach.write(
            _reachable_records(reach.MIN_REACHABLE),
            previous=reach.read_previous_reachable_count(),
        )

    # What the next run will measure itself against is still the last good run.
    assert reach.read_previous_reachable_count() == good


def test_the_floor_is_written_into_the_receipt(tmp_path, monkeypatch):
    """The file carries the constants its verdicts were taken under, so a run
    read months later says which gate produced it (#749's promise)."""
    out = tmp_path / "reach.json"
    monkeypatch.setattr(reach, "OUT_PATH", out)

    reach.write(_reachable_records(reach.MIN_REACHABLE), guard=False)

    assert json.loads(out.read_text())["min_grade_run_ft"] == reach.MIN_GRADE_RUN_FT


# --- the network trails in the union (#1016) --------------------------------
#
# The defect these are about: an OSM spring beside a Harriman trail was fetched,
# clipped into the corridor and then refused for being far from the A.T.,
# because the union it was measured against held only ATC's four layers. Four
# organizations' trails shipped to hikers that way.


# A line well clear of the synthetic centerline - far enough that no A.T.
# feature can be what a point beside it passes on, so a pass here can only be
# the network line.
NETWORK_COORDS = [(lon + 0.20, lat + 0.20) for lon, lat in CENTERLINE_COORDS]


def test_a_spring_beside_a_network_trail_is_reachable(tmp_path, monkeypatch):
    """#1016 in one case. Before this the same point read 'no trail, side
    trail, shelter or campsite within 5 miles'."""
    lon, lat = NETWORK_COORDS[0]
    records = _measure(
        tmp_path,
        monkeypatch,
        [_water(1, lon, lat + JUST_INSIDE_DEG)],
        network_features=[_network_line(NETWORK_COORDS)],
    )

    assert records["1"]["passes_distance"] is True
    assert records["1"]["nearest"] == reach.NETWORK_LINE_TABLE


def test_it_records_whose_trail_the_spring_is_beside(tmp_path, monkeypatch):
    """Reported, never gated on - and read by export_poi.py for a different
    question: a point whose only walk is off the A.T. may not carry an A.T.
    mile, because dayPlanner.ts would offer it as a stop along one."""
    lon, lat = NETWORK_COORDS[0]
    records = _measure(
        tmp_path,
        monkeypatch,
        [_water(1, lon, lat + JUST_INSIDE_DEG)],
        network_features=[_network_line(NETWORK_COORDS, source="mohonk_trails")],
    )

    assert records["1"]["nearest_source"] == "mohonk_trails"


def test_a_point_beside_the_at_carries_no_network_source(tmp_path, monkeypatch):
    """The other direction, and the one that keeps the mile: a point that
    passed on ATC's own centerline is on the A.T. and says nothing about any
    organization's trail."""
    lon, lat = CENTERLINE_COORDS[0]
    records = _measure(
        tmp_path,
        monkeypatch,
        [_water(1, lon, lat)],
        network_features=[_network_line(NETWORK_COORDS)],
    )

    assert records["1"]["nearest"] == "centerline"
    assert "nearest_source" not in records["1"]


def test_the_gate_still_binds_on_a_network_trail(tmp_path, monkeypatch):
    """The radius did not move, only what it is measured from. A fountain 60 m
    from somebody else's trail is as unreachable as one 60 m from the A.T."""
    lon, lat = NETWORK_COORDS[0]
    records = _measure(
        tmp_path,
        monkeypatch,
        [_water(1, lon, lat + WELL_OUTSIDE_DEG)],
        network_features=[_network_line(NETWORK_COORDS)],
    )

    assert records["1"]["passes_distance"] is False
    assert "network trail" in records["1"]["reason"]


def test_no_network_artifact_measures_the_at_alone(tmp_path, monkeypatch):
    """The ordinary state on a publish whose network export was skipped or
    whose licences are held back - it costs what it always cost and must not
    be an error."""
    lon, lat = NETWORK_COORDS[0]
    records = _measure(tmp_path, monkeypatch, [_water(1, lon, lat + JUST_INSIDE_DEG)])

    assert records["1"]["passes_distance"] is False


def test_an_empty_network_artifact_is_not_a_network(tmp_path, monkeypatch):
    lon, lat = NETWORK_COORDS[0]
    records = _measure(tmp_path, monkeypatch, [_water(1, lon, lat + JUST_INSIDE_DEG)], network_features=[])

    assert records["1"]["passes_distance"] is False


# --- resuming across the change (#1016) -------------------------------------


def _verdict_file(tmp_path, **payload):
    path = tmp_path / "osm_water_reach.json"
    path.write_text(json.dumps({"points": [], **payload}))
    return path


def test_verdicts_taken_without_the_network_are_remeasured(tmp_path):
    """The trap this exists to spring. The publish workflow restores the last
    run's verdicts and RESUMES rather than rebuilding, so without this the run
    that finally has the network lines would resume A.T.-only verdicts and
    publish them - the defect surviving its own fix.
    """
    network = tmp_path / "nearby_trails.geojson"
    network.write_text("{}")
    on_disk = _verdict_file(tmp_path, measured_against_network=False)

    assert reach.network_union_changed(on_disk, network) is True


def test_a_file_predating_the_stamp_is_remeasured_once(tmp_path):
    """No key at all is every verdict file written before #1016 - the migration
    case, and the reason absence is read as false rather than as unknown."""
    network = tmp_path / "nearby_trails.geojson"
    network.write_text("{}")

    assert reach.network_union_changed(_verdict_file(tmp_path), network) is True


def test_verdicts_already_taken_against_the_network_are_kept(tmp_path):
    network = tmp_path / "nearby_trails.geojson"
    network.write_text("{}")
    on_disk = _verdict_file(tmp_path, measured_against_network=True)

    assert reach.network_union_changed(on_disk, network) is False


def test_a_vanished_network_artifact_does_not_discard_good_verdicts(tmp_path):
    """One direction only, deliberately: re-measuring here would throw away
    verdicts taken against a wider union to replace them with a narrower set.
    Those points fail the export's own gate if their lines stop publishing,
    which is the safe direction and how a held-back licence already behaves."""
    on_disk = _verdict_file(tmp_path, measured_against_network=True)

    assert reach.network_union_changed(on_disk, tmp_path / "gone.geojson") is False


def test_a_review_only_organizations_lines_are_not_measured_against(tmp_path, monkeypatch):
    """The state every organization is registered in - `reaches_hikers: false`
    until somebody answers about terms - and the one that would otherwise be a
    new defect rather than an old one.

    The artifact holds every EXPORTED source so a reviewer can look at the map
    before the answer arrives. Measuring against a held-back one would derive a
    PUBLISHED water pin from lines nobody may publish, and draw it over ground
    where the app shows no trail at all, because publish.py holds the whole
    artifact back when any source in it is held back.
    """
    lon, lat = NETWORK_COORDS[0]
    records = _measure(
        tmp_path,
        monkeypatch,
        [_water(1, lon, lat + JUST_INSIDE_DEG)],
        network_features=[_network_line(NETWORK_COORDS, source="dec_catskills_trails")],
        shipped=set(),
    )

    assert records["1"]["passes_distance"] is False


def test_a_shipping_organization_beside_a_held_back_one_still_counts(tmp_path, monkeypatch):
    """Per source, not all-or-nothing: one steward waiting on terms must not
    take another steward's water off the map."""
    lon, lat = NETWORK_COORDS[0]
    records = _measure(
        tmp_path,
        monkeypatch,
        [_water(1, lon, lat + JUST_INSIDE_DEG)],
        network_features=[
            _network_line(NETWORK_COORDS, source="dec_catskills_trails"),
            _network_line(NETWORK_COORDS, source="oprhp_trails"),
        ],
        shipped={"oprhp_trails"},
    )

    assert records["1"]["passes_distance"] is True
    assert records["1"]["nearest_source"] == "oprhp_trails"
