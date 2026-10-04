"""step_osm_water.py and step_osm_water_grade.py: OSM water's points into derived.osm_water, and the grade half of their reach into derived.osm_water_grade (PO03, PO06, PO07).

The rules are build_osm_water_reach.py's and fetch_trail_water.py's, and their
own tests hold them (tests/test_build_osm_water_reach.py,
tests/test_fetch_trail_water.py); these hold the steps to them: the points
landed as the file holds them, the grade loop and the write guards called
rather than copied, no checkpoint left where the script resumes from, and
the network never reached. Synthetic geometry throughout and no request made
(TESTING.md).
"""

import json
from datetime import UTC, datetime

import duckdb
import pytest

import build_osm_water_reach
import make_dbt_fixtures
import step_osm_water
import step_osm_water_grade

LOADED = datetime(2026, 10, 2, tzinfo=UTC)


def _reach_table(path, rows, points=None):
    """A warehouse holding int_points_of_interest__osm_water_reach's rows, and derived.osm_water's when given."""
    with duckdb.connect(str(path)) as con:
        con.execute("create schema intermediate")
        con.execute(
            "create table intermediate.int_points_of_interest__osm_water_reach (osm_id varchar, lon double, lat double, "
            "nearest varchar, nearest_source varchar, nearest_m varchar, walk_lon double, walk_lat double, "
            "passes_distance boolean, reason varchar)"
        )
        if rows:
            con.executemany(
                "insert into intermediate.int_points_of_interest__osm_water_reach values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
            )
        if points is not None:
            step_osm_water.write_osm_water(con, points, LOADED)


def _grades(path):
    with duckdb.connect(str(path), read_only=True) as con:
        return {
            row[0]: row[1:]
            for row in con.execute(
                "select osm_id, passes_grade, drop_ft, grade, grade_floored, reachable, reason from derived.osm_water_grade"
            ).fetchall()
        }


def _point(osm_id, lon=-74.0, lat=41.0, **tags):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"osm_id": osm_id, **tags}}


# --- step_osm_water ----------------------------------------------------------------------------


def test_the_points_land_as_the_file_holds_them(tmp_path):
    points = tmp_path / "points.geojson"
    points.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    _point("2", kind="spring", intermittent="yes"),
                    {"type": "Feature", "geometry": None, "properties": {"osm_id": "1", "kind": "water_tap"}},
                ],
            }
        )
    )
    assert step_osm_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--points", str(points)]) == 0
    with duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True) as con:
        rows = con.execute("select feature_row, osm_id, kind, lon, lat, properties from derived.osm_water order by 1").fetchall()
    assert [row[:5] for row in rows] == [(0, "2", "spring", -74.0, 41.0), (1, "1", "water_tap", None, None)]
    # An absent tag stays absent: describe_water() reads absence, never a null member.
    assert json.loads(rows[0][5]) == {"osm_id": "2", "kind": "spring", "intermittent": "yes"}


def test_without_a_file_there_is_no_osm_water_and_it_says_why(tmp_path, capsys):
    """A build that names no scan lands no points, and says that is what it did."""
    assert step_osm_water.main(["--warehouse", str(tmp_path / "w.duckdb")]) == 0
    assert step_osm_water.WAITS in capsys.readouterr().out
    with duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True) as con:
        assert con.execute("select count(*) from derived.osm_water").fetchone()[0] == 0


def test_a_named_file_that_is_not_there_is_an_error_not_an_empty_build(tmp_path):
    with pytest.raises(SystemExit):
        step_osm_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--points", str(tmp_path / "absent.geojson")])


def test_the_monthly_builds_landed_scan_lands_as_the_file_holds_it(tmp_path):
    """#1652: build_marts.py --lane monthly passes the scan the build pinned (data/raw/derived/osm_water.geojson)."""
    landed = tmp_path / "derived" / "osm_water.geojson"
    landed.parent.mkdir()
    landed.write_text(json.dumps({"type": "FeatureCollection", "features": [_point("7", kind="spring")]}))

    assert step_osm_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--landed", str(landed)]) == 0
    with duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True) as con:
        assert con.execute("select osm_id, kind from derived.osm_water").fetchall() == [("7", "spring")]


def test_a_monthly_build_with_no_scan_ever_landed_warns_and_lands_no_osm_water(tmp_path, capsys):
    """Before the extract's first complete set and with no earlier scan pinned, the build publishes no OSM water, as
    before #1652, and says so in a warning the run summary shows, never by failing the whole build."""
    assert step_osm_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--landed", str(tmp_path / "absent.geojson")]) == 0

    out = capsys.readouterr().out
    assert "::warning title=No OSM water this build::" in out and step_osm_water.NEVER_LANDED in out
    with duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True) as con:
        assert con.execute("select count(*) from derived.osm_water").fetchone()[0] == 0


def test_points_and_a_landed_scan_are_never_named_together(tmp_path):
    with pytest.raises(SystemExit):
        step_osm_water.main(["--points", str(tmp_path / "a.geojson"), "--landed", str(tmp_path / "b.geojson")])


def test_the_fixture_points_are_in_fetch_osm_water_shape(tmp_path):
    raw = tmp_path / "raw"
    make_dbt_fixtures.write_fixtures(raw)
    features = json.loads((raw / "osm_water" / "points.geojson").read_text())["features"]
    kinds = {"spring", "drinking_water", "water_tap", "water_well"}
    for feature in features:
        properties = feature["properties"]
        assert isinstance(properties["osm_id"], str) and properties["kind"] in kinds
        # fetch_osm_water.py's feature(): the carried tags only where present, never null.
        assert set(properties) <= {"osm_id", "kind", "name", "seasonal", "intermittent", "drinking_water"}
        assert None not in properties.values()
    assert len({feature["properties"]["osm_id"] for feature in features}) == len(features)
    # Not where export_poi.py reads, which would refuse to run without verdicts.
    assert not (raw / "osm_water.geojson").exists()


# --- step_osm_water_grade ----------------------------------------------------------------------

PASSING = ("p", -74.0, 40.9998, "centerline", None, "22.39", -74.0, 41.0, True, None)
FAR = (
    "f",
    -74.0,
    41.3,
    None,
    None,
    None,
    None,
    None,
    False,
    "no trail, side trail, network trail, shelter or campsite within 5 miles",
)
STEEP = ("s", -74.0042, 41.0062, "side_trail", None, "27.93", -74.004, 41.006, True, None)
SHORT = ("t", -74.24, 41.20402, "campsite", None, "2.24", -74.24, 41.204, True, None)
SILENT = ("q", -74.264, 41.2402, "shelter", None, "22.39", -74.264, 41.24, True, None)
ANSWERS = {
    "40.999800,-74.000000": 1000.0,
    "41.000000,-74.000000": 1002.0,
    "41.006200,-74.004200": 980.0,
    "41.006000,-74.004000": 1000.0,
    "41.204020,-74.240000": 997.0,
    "41.204000,-74.240000": 1000.0,
    "41.240000,-74.264000": 1100.0,
}


@pytest.fixture
def answers(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(ANSWERS))
    return path


def test_the_verdicts_are_apply_grade_gates(tmp_path, answers):
    _reach_table(tmp_path / "w.duckdb", [PASSING, FAR, STEEP, SHORT, SILENT])
    assert step_osm_water_grade.main(["--warehouse", str(tmp_path / "w.duckdb"), "--elevations", str(answers)]) == 0
    grades = _grades(tmp_path / "w.duckdb")

    records = step_osm_water_grade.read_reach(duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True))
    live = build_osm_water_reach.elevation_ft, build_osm_water_reach.OUT_PATH
    build_osm_water_reach.elevation_ft = lambda lat, lon: ANSWERS.get(f"{lat:.6f},{lon:.6f}")
    build_osm_water_reach.OUT_PATH = tmp_path / "expected" / "osm_water_reach.json"
    try:
        build_osm_water_reach.apply_grade_gate(records, quiet=True)
        build_osm_water_reach.write(records, guard=False)
    finally:
        build_osm_water_reach.elevation_ft, build_osm_water_reach.OUT_PATH = live
    for record in records:
        passes, drop, grade, floored, reachable, reason = grades[record["osm_id"]]
        assert (passes, drop, grade) == (record.get("passes_grade"), record.get("drop_ft"), record.get("grade")), record
        assert (floored, reachable, reason) == (record.get("grade_floored", False), record["reachable"], record.get("reason"))
    assert {osm_id for osm_id, row in grades.items() if row[4]} == {"p", "t"}
    assert grades["t"][3] is True, "a walk too short to grade passes on the floor"
    assert grades["q"][5] == build_osm_water_reach.NO_ELEVATION


def test_no_checkpoint_is_left_where_the_script_resumes_from(tmp_path, answers, monkeypatch):
    out = tmp_path / "raw" / "osm_water_reach.json"
    monkeypatch.setattr(build_osm_water_reach, "OUT_PATH", out)
    _reach_table(tmp_path / "w.duckdb", [PASSING])
    step_osm_water_grade.main(["--warehouse", str(tmp_path / "w.duckdb"), "--elevations", str(answers)])
    assert build_osm_water_reach.OUT_PATH == out
    assert not out.exists() and not build_osm_water_reach.checkpoint_path().exists()


def test_a_live_run_with_points_and_too_few_reachable_writes_nothing(tmp_path, monkeypatch, capsys):
    """build_osm_water_reach.write()'s MIN_REACHABLE floor, which watches a scan that read no trail geometry."""
    monkeypatch.setattr(build_osm_water_reach, "elevation_ft", lambda lat, lon: 1000.0)
    _reach_table(tmp_path / "w.duckdb", [PASSING], points=[_point("p")])
    assert step_osm_water_grade.main(["--warehouse", str(tmp_path / "w.duckdb"), "--previous", str(tmp_path / "none")]) == 1
    assert "below the floor" in capsys.readouterr().out
    with duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True) as con:
        assert (
            con.execute("select count(*) from information_schema.tables where table_name = 'osm_water_grade'").fetchone()[0] == 0
        )


def test_a_live_run_that_lost_most_of_its_reachable_points_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build_osm_water_reach, "elevation_ft", lambda lat, lon: 1000.0)
    monkeypatch.setattr(build_osm_water_reach, "MIN_REACHABLE", 1)
    previous = tmp_path / "osm_water_reach.json"
    previous.write_text(json.dumps({"n_reachable": 10, "points": []}))
    _reach_table(tmp_path / "w.duckdb", [PASSING], points=[_point("p")])
    assert step_osm_water_grade.main(["--warehouse", str(tmp_path / "w.duckdb"), "--previous", str(previous)]) == 1
    assert "drop guard" in capsys.readouterr().out


def test_a_build_with_no_osm_water_landed_has_nothing_to_guard(tmp_path, capsys):
    """A build with no scan landed (before the extract's first complete set, #1652) has no points, which is no scan
    to have collapsed."""
    _reach_table(tmp_path / "w.duckdb", [], points=[])
    assert step_osm_water_grade.main(["--warehouse", str(tmp_path / "w.duckdb")]) == 0
    assert _grades(tmp_path / "w.duckdb") == {}
    assert "0 corridor OSM water points" in capsys.readouterr().out


def test_the_live_elevation_lookup_is_put_back(tmp_path, answers):
    live = build_osm_water_reach.elevation_ft
    _reach_table(tmp_path / "w.duckdb", [PASSING])
    step_osm_water_grade.main(["--warehouse", str(tmp_path / "w.duckdb"), "--elevations", str(answers)])
    assert build_osm_water_reach.elevation_ft is live


def test_the_step_refuses_to_run_before_the_distance_pass(tmp_path):
    duckdb.connect(str(tmp_path / "w.duckdb")).close()
    with pytest.raises(SystemExit, match="int_points_of_interest__osm_water_reach"):
        step_osm_water_grade.main(["--warehouse", str(tmp_path / "w.duckdb")])
