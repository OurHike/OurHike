"""extract/_fixtures.py: the real extract over make_dbt_fixtures.py's files, into the warehouse CI's dbt job reads.

The run is the extract's own (change checks, pagers, hints, normalize, the
run check, the committed-load read), so what these tests hold is that every
fixture file arrives whole and as dlt names it, and that nothing reaches past
its fixture to the network. conftest.py's socket guard stays on.
"""

import json

import duckdb
import pytest
import requests

import make_dbt_fixtures
from extract._fixtures import FixtureAdapter, build, esri_type, fixture_file, fixture_resources


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    root = tmp_path_factory.mktemp("fixtures")
    make_dbt_fixtures.write_fixtures(root / "raw")
    counts = build(root / "raw", root / "warehouse.duckdb", root / "store")
    return root, counts


def test_every_fixture_file_with_a_resource_lands_whole(fixtures):
    root, counts = fixtures
    resources, _ = fixture_resources(root / "raw")
    assert len(resources) == 56, "55 monthly layers and OPRHP's temporary closures on the hourly lane"
    for resource in resources:
        expected = len(json.loads(fixture_file(root / "raw", resource.key).read_text())["features"])
        assert counts[resource.table] == expected, resource.table


def test_the_tables_are_the_extracts_own_names_and_columns(fixtures):
    root, _ = fixtures
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        tables = {row[0] for row in con.execute("select table_name from duckdb_tables() where schema_name = 'raw'").fetchall()}
        assert {"raw_nysdec__dec_lean_tos", "raw_nysparks__oprhp_trails", "raw_atc__shelters", "raw_opentrail__at"} <= tables
        assert "_extract_runs" in tables
        mohonk = {row[0] for row in con.execute('describe raw."raw_mohonk__mohonk_trails"').fetchall()}
        assert "use" in mohonk and "use_" not in mohonk, "the upstream's own spelling, where GDAL's ST_Read wrote use_"
        assert "ogc_fid" not in mohonk, "no reader-invented row id"
        con.execute("INSTALL spatial; LOAD spatial;")
        (kind,) = con.execute(
            'select st_geometrytype(st_geomfromgeojson(geometry::varchar)) from raw."raw_atc__shelters" limit 1'
        ).fetchone()
        assert kind == "POINT"
        assert con.execute('select feature_id from raw."raw_opentrail__at"').fetchall(), "hinted, so it exists while null"


def test_a_url_with_no_fixture_fails_rather_than_reaching_the_network():
    session = requests.Session()
    session.mount("https://", FixtureAdapter({}, {}, {}))
    with pytest.raises(requests.ConnectionError, match="fixture mode has no answer"):
        session.get("https://services.arcgis.com/elsewhere/FeatureServer/0", params={"f": "json"})


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1, 2, None], "esriFieldTypeInteger"),
        ([1, 2.5], "esriFieldTypeDouble"),
        (["Y", None], "esriFieldTypeString"),
        ([None, None], "esriFieldTypeString"),
    ],
)
def test_a_fields_type_is_read_off_the_fixtures_own_values(values, expected):
    assert esri_type(values) == expected
