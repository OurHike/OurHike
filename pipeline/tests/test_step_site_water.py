"""step_site_water.py: fetch_trail_water.py's site water, over the warehouse's sites, into derived.site_water (PO07, PO17).

The rule is fetch_trail_water.py's and its own tests hold it
(tests/test_fetch_trail_water.py); these hold the step to it: the sites in
fetch_atc_features' order, the derivation its build() makes, the two
refusals it writes nothing after, and the two ways in that never reach the
network, on make_dbt_fixtures.py's own fixture inputs. Synthetic geometry
throughout and no request made (TESTING.md).
"""

import json
from datetime import UTC, datetime

import duckdb
import pytest

import fetch_trail_water
import make_dbt_fixtures
import step_site_water

LOADED = datetime(2026, 10, 2, tzinfo=UTC)


def _warehouse(path, sites):
    """A warehouse holding int_points_of_interest__water_sites' rows."""
    with duckdb.connect(str(path)) as con:
        con.execute("create schema intermediate")
        con.execute(
            "create table intermediate.int_points_of_interest__water_sites "
            "(layer varchar, global_id varchar, name varchar, lat double, lon double)"
        )
        if sites:
            con.executemany("insert into intermediate.int_points_of_interest__water_sites values (?, ?, ?, ?, ?)", sites)


def _rows(path):
    with duckdb.connect(str(path), read_only=True) as con:
        return con.execute(
            "select site_row, layer, atc_global_id, atc_name, water, unresolved, candidate from derived.site_water order by site_row"
        ).fetchall()


@pytest.fixture
def fixture_inputs(tmp_path):
    """make_dbt_fixtures.py's shelters and campsites, and the candidates and EPQS answers it writes for them."""
    raw = tmp_path / "raw"
    make_dbt_fixtures.write_fixtures(raw)
    sites = []
    for layer in step_site_water.LAYERS:
        for feature in json.loads((raw / f"{layer}.geojson").read_text())["features"]:
            if feature.get("geometry"):
                lon, lat = feature["geometry"]["coordinates"]
                sites.append((layer, feature["properties"]["GlobalID"], feature["properties"].get("Name"), lat, lon))
    return raw, sites


def test_the_sites_come_in_fetch_atc_features_order():
    con = duckdb.connect()
    con.execute("create table sites (layer varchar, global_id varchar, name varchar, lat double, lon double)")
    con.executemany(
        "insert into sites values (?, ?, ?, ?, ?)",
        [
            ("campsites", "c2", "Beta Campsite", 41.0, -74.0),
            ("shelters", "s2", "Alpha Shelter", 41.0, -74.0),
            ("shelters", "s1", "Alpha Shelter", 41.0, -74.0),
            ("shelters", "s0", None, 41.0, -74.0),
            ("campsites", "c1", "Alpha Campsite", 41.0, -74.0),
        ],
    )
    sites = step_site_water.read_sites(con, "sites")
    assert list(sites) == ["shelters", "campsites"]
    assert [row["global_id"] for row in sites["shelters"]] == ["s0", "s1", "s2"]
    assert [row["global_id"] for row in sites["campsites"]] == ["c1", "c2"]


def test_the_step_writes_what_fetch_trail_water_builds_from_the_same_inputs(tmp_path, fixture_inputs):
    raw, sites = fixture_inputs
    _warehouse(tmp_path / "w.duckdb", sites)
    code = step_site_water.main(
        [
            "--warehouse",
            str(tmp_path / "w.duckdb"),
            "--candidates",
            str(raw / "site_water" / "candidates.json"),
            "--elevations",
            str(raw / "site_water" / "epqs_elevations.json"),
        ]
    )
    assert code == 0

    answers = json.loads((raw / "site_water" / "epqs_elevations.json").read_text())
    by_layer = {layer: [] for layer in step_site_water.LAYERS}
    for layer, global_id, name, lat, lon in sites:
        by_layer[layer].append({"global_id": global_id, "name": name, "lat": lat, "lon": lon})
    by_layer = {layer: sorted(rows, key=lambda row: (row["name"] or "", row["global_id"])) for layer, rows in by_layer.items()}
    live = fetch_trail_water.elevation_ft
    fetch_trail_water.elevation_ft = lambda lat, lon: answers.get(f"{lat:.6f},{lon:.6f}")
    try:
        expected = fetch_trail_water.build(by_layer, json.loads((raw / "site_water" / "candidates.json").read_text()))["sites"]
    finally:
        fetch_trail_water.elevation_ft = live

    rows = _rows(tmp_path / "w.duckdb")
    assert len(rows) == len(expected)
    for (row, layer, global_id, name, water, unresolved, candidate), record in zip(rows, expected):
        assert (layer, global_id, name) == (record["layer"], record["atc_global_id"], record["atc_name"]), row
        assert (json.loads(water) if water else None) == record["water"], global_id
        assert unresolved == record.get("unresolved"), global_id
        assert (json.loads(candidate) if candidate else None) == record.get("candidate"), global_id


def test_the_fixtures_reach_every_branch_the_gates_have(tmp_path, fixture_inputs):
    raw, sites = fixture_inputs
    _warehouse(tmp_path / "w.duckdb", sites)
    step_site_water.main(
        [
            "--warehouse",
            str(tmp_path / "w.duckdb"),
            "--candidates",
            str(raw / "site_water" / "candidates.json"),
            "--elevations",
            str(raw / "site_water" / "epqs_elevations.json"),
        ]
    )
    rows = _rows(tmp_path / "w.duckdb")
    reasons = {unresolved.split(" ")[0] + " " + unresolved.split(" ")[1] for *_, unresolved, _ in rows if unresolved}
    waters = [json.loads(water) for *_, water, _, _ in rows if water]
    assert {"the nearest", "the ground", "USGS would", "no stream"} <= reasons
    assert any(water["sources"] == ["nhd", "osm"] for water in waters), "two hydrographies merged"
    assert any(water["sources"] == ["osm"] for water in waters), "OSM alone"
    assert any(water["distance_ft"] < fetch_trail_water.MIN_GRADE_RUN_FT for water in waters), "a walk too short to grade"
    assert {water["flow"] for water in waters} >= {"perennial", "intermittent", "ephemeral", None}


def test_a_point_the_answers_do_not_hold_has_no_elevation(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps({"41.000000,-74.000000": 100.0}))
    lookup = step_site_water.offline_elevations(path)
    assert lookup(41.0, -74.0) == 100.0
    assert lookup(41.0, -74.000001) is None


def test_a_derivation_already_made_lands_as_it_is(tmp_path):
    document = {
        "sites": [
            {
                "layer": "shelters",
                "atc_global_id": "g1",
                "atc_name": "One",
                "water": {"lat": 41.0, "lon": -74.0, "sources": ["nhd"]},
            },
            {
                "layer": "campsites",
                "atc_global_id": "g2",
                "atc_name": "Two",
                "water": None,
                "unresolved": "no stream within 400 ft",
            },
        ]
    }
    (tmp_path / "trail_water.json").write_text(json.dumps(document))
    _warehouse(tmp_path / "w.duckdb", [])
    assert (
        step_site_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--from-file", str(tmp_path / "trail_water.json")]) == 0
    )
    rows = _rows(tmp_path / "w.duckdb")
    assert [(row[2], row[5]) for row in rows] == [("g1", None), ("g2", "no stream within 400 ft")]
    assert json.loads(rows[0][4])["sources"] == ["nhd"]


def test_no_derivation_on_disk_is_no_site_water_rather_than_a_failure(tmp_path):
    """export_poi.py's load_trail_water(): a missing file is a normal state."""
    _warehouse(tmp_path / "w.duckdb", [])
    assert step_site_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--from-file", str(tmp_path / "absent.json")]) == 0
    assert _rows(tmp_path / "w.duckdb") == []


def test_a_derivation_that_lost_most_of_its_site_water_writes_nothing(tmp_path, monkeypatch, capsys):
    """fetch_trail_water.py's MAX_SITE_WATER_DROP_RATIO, against the last derivation on disk."""
    previous = tmp_path / "trail_water.json"
    previous.write_text(json.dumps({"sites": [{"water": {"lat": 0, "lon": 0}} for _ in range(10)]}))
    _warehouse(tmp_path / "w.duckdb", [("shelters", "g1", "One", 41.0, -74.0)])
    monkeypatch.setattr(fetch_trail_water, "collect_streams", lambda sites: {})
    code = step_site_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--derive", "--previous", str(previous)])
    assert code == 1
    assert "drop guard" in capsys.readouterr().out
    with duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True) as con:
        assert con.execute("select count(*) from information_schema.tables where table_schema = 'derived'").fetchone()[0] == 0


def test_a_hydrography_read_that_loads_no_streams_writes_nothing(tmp_path, monkeypatch, capsys):
    """fetch_trail_water.py's EMPTY_READ: every dataset it walks has streams, so none is a broken read."""

    def empty(sites):
        raise ValueError(fetch_trail_water.EMPTY_READ.format(label="nhd/0102"))

    _warehouse(tmp_path / "w.duckdb", [("shelters", "g1", "One", 41.0, -74.0)])
    monkeypatch.setattr(fetch_trail_water, "collect_streams", empty)
    argv = ["--warehouse", str(tmp_path / "w.duckdb"), "--derive", "--previous", str(tmp_path / "none.json")]
    assert step_site_water.main(argv) == 1
    assert "loaded no stream reaches" in capsys.readouterr().out


def test_the_live_elevation_lookup_is_put_back_after_an_offline_run(tmp_path, fixture_inputs):
    raw, sites = fixture_inputs
    _warehouse(tmp_path / "w.duckdb", sites)
    live = fetch_trail_water.elevation_ft
    step_site_water.main(
        [
            "--warehouse",
            str(tmp_path / "w.duckdb"),
            "--candidates",
            str(raw / "site_water" / "candidates.json"),
            "--elevations",
            str(raw / "site_water" / "epqs_elevations.json"),
        ]
    )
    assert fetch_trail_water.elevation_ft is live


def test_by_default_the_step_lands_the_last_derivation_and_fetches_nothing(tmp_path, monkeypatch):
    """publish-vector-data.yml's include_trail_water is opt-in, so a run that does not tick it reuses the last file."""
    document = {"sites": [{"layer": "shelters", "atc_global_id": "g1", "atc_name": "One", "water": {"lat": 41.0, "lon": -74.0}}]}
    (tmp_path / "trail_water.json").write_text(json.dumps(document))
    monkeypatch.setattr(fetch_trail_water, "OUT_PATH", tmp_path / "trail_water.json")

    def no_network(sites):
        raise AssertionError("the default run read the hydrography")

    monkeypatch.setattr(fetch_trail_water, "collect_streams", no_network)
    _warehouse(tmp_path / "w.duckdb", [("shelters", "g1", "One", 41.0, -74.0)])
    assert step_site_water.main(["--warehouse", str(tmp_path / "w.duckdb")]) == 0
    assert [row[2] for row in _rows(tmp_path / "w.duckdb")] == ["g1"]


def test_a_derivation_from_files_reads_both_files(tmp_path):
    _warehouse(tmp_path / "w.duckdb", [])
    with pytest.raises(SystemExit):
        step_site_water.main(["--warehouse", str(tmp_path / "w.duckdb"), "--candidates", str(tmp_path / "c.json")])
