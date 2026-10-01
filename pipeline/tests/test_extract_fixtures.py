"""extract/_fixtures.py: the real extract over make_dbt_fixtures.py's files, into the warehouse CI's dbt job reads.

The run is the extract's own (change checks, pagers, hints, normalize, the
run check, the committed-load read), so what these tests hold is that every
fixture file arrives whole and as dlt names it, and that nothing reaches past
its fixture to the network. conftest.py's socket guard stays on.
"""

import json
from pathlib import Path

import duckdb
import pytest
import requests

import make_dbt_fixtures
from extract._fixtures import FixtureAdapter, build, esri_type, fixture_file, fixture_resources
from extract._kinds import ReviewedFile


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    root = tmp_path_factory.mktemp("fixtures")
    make_dbt_fixtures.write_fixtures(root / "raw")
    counts = build(root / "raw", root / "warehouse.duckdb", root / "store")
    return root, counts


def test_every_fixture_file_with_a_resource_lands_whole(fixtures):
    root, counts = fixtures
    resources, _ = fixture_resources(root / "raw")
    fetched = [r for r in resources if not isinstance(r, ReviewedFile)]
    assert len(fetched) == 56, "55 monthly layers and OPRHP's temporary closures on the hourly lane"
    for resource in fetched:
        expected = len(json.loads(fixture_file(root / "raw", resource.key).read_text())["features"])
        assert counts[resource.table] == expected, resource.table


def test_the_reviewed_files_land_from_git_whole(fixtures):
    root, counts = fixtures
    reviewed = [r for r in fixture_resources(root / "raw")[0] if isinstance(r, ReviewedFile)]
    assert {r.table for r in reviewed} >= {"raw_podcasts__podcast_episodes", "raw_ourhike__poi_identity"}
    for resource in reviewed:
        document = json.loads(resource.file.read_text())
        assert counts[resource.table] == len(document[resource.rows_key]), resource.table


def test_a_verbatim_reviewed_file_lands_each_row_as_its_reviewer_wrote_it(fixtures):
    """The podcast episodes land whole, so the gate in dbt sees field names and JSON types as written (ReviewedFile)."""
    root, _ = fixtures
    episodes = json.loads((Path(make_dbt_fixtures.__file__).parent / "reference" / "podcast_episodes.json").read_text())
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        columns = {row[0] for row in con.execute('describe raw."raw_podcasts__podcast_episodes"').fetchall()}
        rows = con.execute('select row_json from raw."raw_podcasts__podcast_episodes" order by _row').fetchall()
    assert columns == {"row_json", "_row", "_file", "_path", "_loaded_at", "_dlt_load_id", "_dlt_id"}
    assert [json.loads(text) for (text,) in rows] == episodes["episodes"]


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


def test_every_raw_table_stamps_loaded_at_with_one_type(fixtures):
    """A proven-empty table (reference/work_projects.json has no rows today) is made by _warehouse.py, not by dlt,
    and must not differ from a loaded one: a mart contract on `_loaded_at` would otherwise fail on an empty table."""
    root, _ = fixtures
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        types = con.execute(
            "select data_type, list(table_name order by table_name) from duckdb_columns() "
            "where schema_name = 'raw' and column_name = '_loaded_at' group by data_type"
        ).fetchall()
    assert [data_type for data_type, _ in types] == ["TIMESTAMP WITH TIME ZONE"], types


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


def test_relative_paths_work_as_ci_passes_them(tmp_path, monkeypatch):
    """pipeline-tests.yml runs `--raw-dir data/raw --warehouse data/warehouse.duckdb` from pipeline/: relative paths."""
    make_dbt_fixtures.write_fixtures(tmp_path / "data" / "raw")
    monkeypatch.chdir(tmp_path)
    counts = build(Path("data/raw"), Path("data/warehouse.duckdb"), Path("data/fixture-store"))
    assert counts["raw_atc__shelters"] == 3
