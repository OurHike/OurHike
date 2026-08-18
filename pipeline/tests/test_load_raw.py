"""Tests for load_raw.py - the L of the ELT layer (pipeline/DBT.md, #100).

Small synthetic GeoJSON fixtures built in test code, a tmp_path warehouse,
never the real fetched data - the usual TESTING.md posture. What matters
here: the registry (not a glob) decides what loads, raw columns arrive
untouched plus the two underscore-prefixed bookkeeping columns, a missing
file is reported-and-skipped rather than fatal, and a re-run replaces
rather than appends.
"""

import json

import duckdb
import pytest

import load_raw


def _write_points(path, names):
    features = [
        {
            "type": "Feature",
            "properties": {"GlobalID": f"g-{i}", "Name": name},
            "geometry": {"type": "Point", "coordinates": [-74.0, 41.0 + i * 0.01]},
        }
        for i, name in enumerate(names)
    ]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


@pytest.fixture()
def con():
    connection = duckdb.connect()
    yield connection
    connection.close()


def test_the_registry_decides_what_loads_not_a_glob():
    """sources.json's ArcGIS layers plus the hand-registered opentrail row,
    and nothing else - an entry with a `kind` (club PDFs, watched-only
    registrations) has no per-feature GeoJSON to load and must not appear."""
    layers = load_raw.registered_layers()

    assert ("atc", "shelters", "shelters.geojson") in layers
    assert ("atc", "half_mile_points_from_springer", "half_mile_points_from_springer.geojson") in layers
    assert ("opentrail", "at", "opentrail_at.geojson") in layers
    keys = {key for _, key, _ in layers}
    assert "osm_water" not in keys, "kind-carrying registry entries are other shapes, not loadable layers"
    assert "usdm_drought" not in keys


def test_loads_into_provider_prefixed_raw_tables_with_bookkeeping(tmp_path, con):
    _write_points(tmp_path / "shelters.geojson", ["A Shelter", "B Shelter"])

    loaded, skipped = load_raw.load_raw(con, tmp_path)

    assert "raw_atc__shelters" in loaded
    rows = con.execute(
        'select "GlobalID", "Name", _loaded_at, _source_path from raw.raw_atc__shelters order by "GlobalID"'
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] == "g-0"
    assert rows[0][1] == "A Shelter"
    assert rows[0][2] is not None, "_loaded_at must record when this load ran"
    assert rows[0][3].endswith("shelters.geojson")


def test_a_registered_but_unfetched_layer_is_skipped_and_reported(tmp_path, con):
    """The loader's contract is 'everything fetched is loaded', not
    'everything registered is fetched' - a partial local fetch must not make
    the warehouse unbuildable, and must not be silent either."""
    _write_points(tmp_path / "shelters.geojson", ["Only Shelter"])

    loaded, skipped = load_raw.load_raw(con, tmp_path)

    assert loaded == ["raw_atc__shelters"]
    assert "campsites.geojson" in skipped
    assert "opentrail_at.geojson" in skipped


def test_a_rerun_replaces_rather_than_appends(tmp_path, con):
    """The warehouse mirrors the newest fetch; stale rows from an older one
    accumulating silently would make every downstream count a lie."""
    _write_points(tmp_path / "shelters.geojson", ["One", "Two"])
    load_raw.load_raw(con, tmp_path)
    _write_points(tmp_path / "shelters.geojson", ["Only"])

    load_raw.load_raw(con, tmp_path)

    count = con.execute("select count(*) from raw.raw_atc__shelters").fetchone()[0]
    assert count == 1


def test_geometry_survives_as_real_geometry(tmp_path, con):
    """The staging models read coordinates with st_x/st_y, so the raw layer
    must land as GEOMETRY, not as a stringified shadow of one."""
    _write_points(tmp_path / "shelters.geojson", ["A Shelter"])

    load_raw.load_raw(con, tmp_path)

    lon, lat = con.execute("select st_x(geom), st_y(geom) from raw.raw_atc__shelters").fetchone()
    assert lon == pytest.approx(-74.0)
    assert lat == pytest.approx(41.0)


def test_provider_slug_is_the_first_word_lowercased():
    assert load_raw._provider_slug("ATC") == "atc"
    assert load_raw._provider_slug("OpenStreetMap contributors") == "openstreetmap"


def test_main_returns_the_report_it_printed(tmp_path):
    _write_points(tmp_path / "shelters.geojson", ["A Shelter"])
    warehouse = tmp_path / "warehouse.duckdb"

    report = load_raw.main(warehouse_path=warehouse, raw_dir=tmp_path)

    assert report["loaded"] == {"raw_atc__shelters": 1}
    assert "campsites.geojson" in report["skipped"]
    assert warehouse.exists()
