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
    """sources.json's ArcGIS layers - BOTH kinds - plus the hand-registered
    opentrail row, and nothing else. A club PDF, a published notice page, a
    watched-only registration, a Geofabrik extract and a weekly national
    polygon file are other shapes with no per-feature GeoJSON at these
    paths, and must not appear."""
    layers = load_raw.registered_layers()

    assert ("atc", "shelters", "shelters.geojson") in layers
    assert ("atc", "half_mile_points_from_springer", "half_mile_points_from_springer.geojson") in layers
    assert ("opentrail", "at", "opentrail_at.geojson") in layers
    keys = {key for _, key, _ in layers}
    assert "osm_water" not in keys, "kind-carrying registry entries are other shapes, not loadable layers"
    assert "usdm_drought" not in keys
    assert "usgs_3dhp" not in keys, "a watched-only registration has no file at all"
    assert "gatc_water_sources" not in keys
    assert "atc_trail_updates" not in keys, "a published notice page is not a feature layer"
    assert "nynjtc_trail_alerts" not in keys


def test_the_other_organizations_layers_load_too():
    """Phase D's actual defect (#100). The filter here used to be
    `kind is None`, which is the twelve A.T. layers and only those - so
    NYNJTC's, OPRHP's, DEC's and Mohonk's layers were fetched, exported and
    on hikers' phones while the warehouse could not see one row of them.
    """
    layers = load_raw.registered_layers()

    assert ("dec", "dec_lean_tos", "external/dec_lean_tos.geojson") in layers
    assert ("oprhp", "oprhp_trails", "external/oprhp_trails.geojson") in layers
    assert ("nynjtc", "nynjtc_long_path", "external/nynjtc_long_path.geojson") in layers
    assert ("mohonk", "mohonk_trails", "external/mohonk_trails.geojson") in layers


def test_an_external_layer_reads_from_fetch_external_layers_own_directory():
    """The two fetchers write to different directories and this loader
    carries that difference rather than flattening it. Spelled out here
    because load_raw.py names the subdirectory in a constant of its own
    rather than importing it from the fetcher - which is one more place the
    two could drift apart."""
    import fetch_external_layers

    assert fetch_external_layers.RAW_DIR.name == load_raw.EXTERNAL_SUBDIR
    assert fetch_external_layers.RAW_DIR.parent == load_raw.RAW_DIR


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
    assert "external/dec_lean_tos.geojson" in skipped, (
        "an unfetched external layer must be reported by the path it would have been fetched to"
    )


def test_an_external_layer_lands_in_a_provider_named_table(tmp_path, con):
    """The end of the Phase D chain, through the real loader: a DEC file in
    fetch_external_layers.py's subdirectory becomes raw_dec__<key> with its
    upstream column names intact."""
    external = tmp_path / load_raw.EXTERNAL_SUBDIR
    external.mkdir()
    (external / "dec_lean_tos.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"OBJECTID": 7, "NAME": "A Lean-to", "PUBLICUSE": "Y"},
                        "geometry": {"type": "Point", "coordinates": [-74.0, 43.5]},
                    }
                ],
            }
        )
    )

    loaded, _ = load_raw.load_raw(con, tmp_path)

    assert "raw_dec__dec_lean_tos" in loaded
    row = con.execute('select "OBJECTID", "NAME", "PUBLICUSE" from raw.raw_dec__dec_lean_tos').fetchone()
    assert row == (7, "A Lean-to", "Y")


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


def test_a_one_word_provider_is_its_own_slug():
    assert load_raw._provider_slug("ATC") == "atc"
    assert load_raw._provider_slug("NYNJTC") == "nynjtc"


def test_a_multi_word_provider_comes_from_the_table_not_from_its_first_word():
    """The bug this replaced (#100, Phase D): `NYS OPRHP` and `NYS DEC` both
    have the first word `NYS`, so a first-word rule named two different
    agencies' tables after the state. The keys kept the table names unique,
    which is exactly why nobody would have noticed."""
    assert load_raw._provider_slug("NYS OPRHP") == "oprhp"
    assert load_raw._provider_slug("NYS DEC") == "dec"
    assert load_raw._provider_slug("Mohonk Preserve") == "mohonk"


def test_an_unmapped_multi_word_provider_raises_rather_than_guessing():
    """Loudly, at load time. A wrong table name is not the kind of thing
    anybody re-reads once the build is green, so the next organization with
    a multi-word provider gets a failure naming the constant to edit."""
    with pytest.raises(ValueError, match="PROVIDER_SLUGS"):
        load_raw._provider_slug("OpenStreetMap contributors")


def test_every_registered_provider_has_a_slug():
    """The guard above only helps if something exercises it. This walks the
    real registry, so a provider added to sources.json without a slug fails
    in pytest rather than in the middle of a warehouse build."""
    load_raw.registered_layers()


def test_main_returns_the_report_it_printed(tmp_path):
    _write_points(tmp_path / "shelters.geojson", ["A Shelter"])
    warehouse = tmp_path / "warehouse.duckdb"

    report = load_raw.main(warehouse_path=warehouse, raw_dir=tmp_path)

    assert report["loaded"] == {"raw_atc__shelters": 1}
    assert "campsites.geojson" in report["skipped"]
    assert warehouse.exists()
