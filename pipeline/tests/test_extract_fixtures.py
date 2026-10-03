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

import export_conditions
import make_dbt_fixtures
from extract._fixtures import (
    JSON_API_DIR,
    JSON_API_KINDS,
    FixtureAdapter,
    FixtureConnection,
    build,
    esri_type,
    fixture_file,
    fixture_resources,
)
from extract._kinds import (
    AtcTrailUpdatePages,
    ConditionsQuery,
    GuidePages,
    NwsAlerts,
    PublishedHikes,
    ReviewedDir,
    ReviewedFile,
    WordpressPosts,
    WordpressTerms,
)


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    root = tmp_path_factory.mktemp("fixtures")
    make_dbt_fixtures.write_fixtures(root / "raw")
    counts = build(root / "raw", root / "warehouse.duckdb", root / "store")
    return root, counts


def test_every_fixture_file_with_a_resource_lands_whole(fixtures):
    root, counts = fixtures
    resources, _ = fixture_resources(root / "raw")
    answered = (
        ReviewedFile
        | ReviewedDir
        | NwsAlerts
        | WordpressPosts
        | WordpressTerms
        | ConditionsQuery
        | PublishedHikes
        | AtcTrailUpdatePages
        | GuidePages
    )
    fetched = [r for r in resources if not isinstance(r, answered) and not isinstance(r, JSON_API_KINDS)]
    assert len(fetched) == 319, (
        "61 monthly layers and OPRHP's temporary closures on the hourly lane, and decision 53's 76 ArcGIS "
        "closure and warning layers: 70 hourly, 3 daily, 3 monthly, and decision 54's 83 places layers, all "
        "monthly, and its 98 trail-line layers, all monthly"
    )
    for resource in fetched:
        expected = len(json.loads(fixture_file(root / "raw", resource.key).read_text())["features"])
        assert counts[resource.table] == expected, resource.table


def test_atcs_z_centerline_lands_its_z_and_its_rows_with_no_geometry(fixtures):
    """`return_z` end to end in CI's build: Esri JSON pages, the conversion, dlt, and ST_GeomFromGeoJSON keep the Z."""
    root, counts = fixtures
    assert counts["raw_atc__atc_atx_centerline"] == 3
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        con.execute("LOAD spatial")
        rows = con.execute(
            "select objectid, case when geometry is null then null"
            " else st_z(st_startpoint(st_geomfromgeojson(geometry::varchar))) end"
            ' from raw."raw_atc__atc_atx_centerline" order by objectid'
        ).fetchall()
    assert rows == [(1, 330.5), (2, 1149.9), (3, None)], "metres as served, and the live layer's geometry-less repeat"


def test_a_club_trail_line_layers_person_fields_never_land_and_the_fields_its_row_clears_do(fixtures):
    """Decision 54's trail lines: a row's `person_fields` never reach the raw table, and its `not_person_fields` do.

    NCTA's spurs name surveyors in `source` (an ordinary name, so only the row's
    list catches it) and carry land-holder classes in `owner` (person-shaped by
    name, so only the row's clearance lets it load); TDEC's 2025 layer names
    staff in `SOURCE` beside editor accounts in CREATED_BY and EDITED_BY.
    """
    root, counts = fixtures
    assert counts["raw_ncta__ncta_spurs"] == 2 and counts["raw_cumberland__tdec_public_trails"] == 2
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        spurs = {
            row[0]
            for row in con.execute(
                "select column_name from information_schema.columns where table_name = 'raw_ncta__ncta_spurs'"
            ).fetchall()
        }
        tdec = {
            row[0]
            for row in con.execute(
                "select column_name from information_schema.columns where table_name = 'raw_cumberland__tdec_public_trails'"
            ).fetchall()
        }
    assert "source" not in spurs and "owner" in spurs and "seg_name" in spurs
    assert not {"source", "created_by", "edited_by"} & tdec and "tr_name" in tdec


def test_the_arizona_trails_z_lands_on_every_vertex(fixtures):
    """ATA's layer 3 carries `return_z`, so its fixture's Z survives the Esri JSON pages and dlt, like ATC's."""
    root, counts = fixtures
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        con.execute("LOAD spatial")
        zs = con.execute(
            "select st_z(st_startpoint(st_geomfromgeojson(geometry::varchar)))"
            ' from raw."raw_ata__ata_arizona_trail" order by objectid'
        ).fetchall()
    assert zs == [(5505.0,), (5605.0,)], "feet as served; staging forces 2-D for the network"


def test_the_long_path_guide_lands_one_row_per_page_its_index_links(fixtures):
    """The guide_pages kind's own parser over make_dbt_fixtures.py's pages, served at the URLs it asks for (PO36)."""
    root, counts = fixtures
    folder = root / "raw" / "guide_pages" / "nynjtc_long_path_guide"
    pages = json.loads((folder / "pages.json").read_text())
    assert counts["raw_nynjtc__nynjtc_long_path_guide"] == len(pages) - 1, (
        "every section page the index links, the index not a row"
    )


def test_the_hourly_lanes_other_upstreams_land_from_their_conditions_answers(fixtures):
    """NWS, NYNJTC's WordPress and OurHike's Postgres, each served from make_dbt_fixtures.py's conditions/ files."""
    root, counts = fixtures
    nws = json.loads((root / "raw" / "conditions" / "nws_alerts.json").read_text())
    nynjtc = json.loads((root / "raw" / "conditions" / "nynjtc_trail_alerts.json").read_text())
    postgres = json.loads((root / "raw" / "conditions" / "ourhike_postgres.json").read_text())
    assert counts["raw_nws__alerts"] == len(nws["features"]), "every alert lands, Cancel and Test too: staging's relay drops them"
    assert counts["raw_nynjtc__nynjtc_trail_alerts"] == len(nynjtc["posts"])
    assert counts["raw_nynjtc__nynjtc_trail_alerts_terms"] == sum(len(terms) for terms in nynjtc["terms"].values())
    for artifact in ("closures", "reports", "notes", "disputes"):
        assert counts[f"raw_ourhike__{artifact}"] == len(postgres[artifact]["rows"]), artifact


#: Each JSON API notice source's table, and the rows make_dbt_fixtures.py's answers hold for it.
JSON_API_ROWS = {
    "raw_nps__nps_alerts": 3,
    "raw_nps__nps_road_events": 2,
    "raw_pasda__pa_dcnr_park_advisories": 2,
    "raw_usgs__usgs_elevated_volcanoes": 2,
    "raw_tehcc__tehcc_wiki_announcements": 2,
    "raw_ouachita__foot_trail_condition_report": 3,
    "raw_fmst__fmst_helene_status": 3,
}


def test_the_json_api_notice_sources_land_from_their_answers_with_no_nps_key_in_the_environment(fixtures):
    """Every extract/_json_apis.py resource answered from conditions/json_apis/, NPS's two under fixture mode's placeholder key."""
    root, counts = fixtures
    resources, _ = fixture_resources(root / "raw")
    landed = {r.table for r in resources if isinstance(r, JSON_API_KINDS)}
    assert landed == set(JSON_API_ROWS)
    assert all((root / "raw" / "conditions" / JSON_API_DIR / f"{r.key}.json").exists() for r in resources if r.table in landed)
    assert {table: counts[table] for table in JSON_API_ROWS} == JSON_API_ROWS


def test_the_lead_advisory_and_the_sheets_person_columns_reach_the_warehouse_as_their_readers_decide(fixtures):
    """The fixture's lead-contamination advisory arrives whole; the sheet's two person columns arrive nowhere."""
    root, _ = fixtures
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        (message,) = con.execute("select message from raw.raw_pasda__pa_dcnr_park_advisories where isalert").fetchone()
        sheet = {row[0] for row in con.execute("describe raw.raw_ouachita__foot_trail_condition_report").fetchall()}
        values = json.dumps(con.execute("select * from raw.raw_ouachita__foot_trail_condition_report").fetchall(), default=str)
    assert "contaminated by lead" in message and "drinking water source" in message
    assert not {"adopted_by", "source_of_last_condition_report"} & sheet
    assert "Fixture Adopter" not in values and "Fixture Reporter" not in values


def test_atcs_pages_land_one_row_per_update_the_fixture_sitemap_lists(fixtures):
    """ATC's site served from conditions/atc_trail_updates.json: the sitemap's every update, each parsed from its page."""
    root, counts = fixtures
    assert counts["raw_atc__atc_trail_updates_pages"] == len(make_dbt_fixtures.ATC_FIXTURE_UPDATES)
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        slugs = {slug for (slug,) in con.execute("select slug from raw.raw_atc__atc_trail_updates_pages").fetchall()}
    assert slugs == {slug for slug, *_ in make_dbt_fixtures.ATC_FIXTURE_UPDATES}


def test_the_hike_finder_lands_every_page_its_listing_links_through_the_real_parse(fixtures):
    """PublishedHikes reads make_dbt_fixtures.py's listing, pages and GPX through lib/hikefinder.py: every page lands,
    a coordinate outside the NYNJTC box lands as no start, and a GPX holding no point lands as no track."""
    root, counts = fixtures
    hikes = make_dbt_fixtures._HIKEFINDER_HIKES
    assert counts["raw_nynjtc__nynjtc_hike_finder"] == len(hikes)
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        rows = {
            hike_id: (start, gpx)
            for hike_id, start, gpx in con.execute('select id, start, gpx from raw."raw_nynjtc__nynjtc_hike_finder"').fetchall()
        }
    assert set(rows) == {hike_id for hike_id, *_ in hikes}
    assert rows[9][0] is None, "hike 9's coordinate is 0,0, which lib/hikefinder.py's _in_range() refuses"
    assert rows[4][1] is not None and "<trkpt" in rows[4][1], "hike 4's GPX lands as served"
    assert rows[11][1] is None, "hike 11's GPX holds no point, so PublishedHikes lands no track"


def test_conditions_rows_land_in_the_shapes_their_real_kinds_give_them(fixtures):
    """The column hints are the real kinds': NWS's text stays text, a Postgres timestamp is a timestamp, a person never lands."""
    root, _ = fixtures
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:

        def columns(table: str) -> dict[str, str]:
            return dict(
                con.execute(f"select column_name, data_type from duckdb_columns() where table_name = '{table}'").fetchall()
            )

        nws = columns("raw_nws__alerts")
        assert nws["sent"] == "VARCHAR", "NWS's own offset stays in the text the phone is relayed"
        assert nws["instruction"] == "VARCHAR", "hinted, so the column exists though one alert's is null"
        posts = columns("raw_nynjtc__nynjtc_trail_alerts")
        assert {"author", "yoast_head", "yoast_head_json"}.isdisjoint(posts), "WP_DROPPED: the fields that name a person"
        assert posts["title"] == "VARCHAR" and posts["park"] == "VARCHAR", "nested values stay one JSON column each"
        closures = columns("raw_ourhike__closures")
        assert closures["verified_at"] == "TIMESTAMP WITH TIME ZONE"
        assert {"reported_by", "verified_by"}.isdisjoint(closures), "the query withholds who reported and who verified"
        assert columns("raw_ourhike__disputes")["accounts"] == "BIGINT"


@pytest.mark.parametrize(
    "artifact, order",
    [
        ("closures", ("start_mile_marker", "id")),
        ("reports", ("timestamp", "id")),
        ("notes", ("observed_at", "id")),
        ("disputes", ("poi_id",)),
    ],
)
def test_the_stand_in_postgres_rows_are_in_each_querys_own_order(artifact, order):
    """FixtureConnection hands rows back as make_dbt_fixtures.py wrote them and sorts nothing, so the rows are written
    in each PUBLIC_*_SQL's ORDER BY: parity.py reads export_conditions.py's documents through the same connection."""
    rows = make_dbt_fixtures.closures_and_warnings_fixtures()["conditions/ourhike_postgres.json"]
    written = json.loads(rows)[artifact]["rows"]
    assert written == sorted(written, key=lambda row: tuple(row[name] for name in order))


def test_the_stand_in_postgres_answers_only_the_extracts_own_sql():
    """A query the extract does not send gets no canned answer: it fails, so a changed query cannot pass on a stale one."""
    connection = FixtureConnection({"closures": {"columns": [["id", "varchar"]], "rows": [{"id": "x"}]}})
    with pytest.raises(RuntimeError, match="no answer"):
        connection.execute("SELECT * FROM public.closures")
    assert connection.execute(export_conditions.TABLE_EXISTS_SQL, ("public.closures",)).fetchone() == (True,)


def test_the_reviewed_files_land_from_git_whole(fixtures):
    root, counts = fixtures
    reviewed = [r for r in fixture_resources(root / "raw")[0] if isinstance(r, ReviewedFile)]
    assert {r.table for r in reviewed} >= {
        "raw_podcasts__podcast_episodes",
        "raw_ourhike__poi_identity",
        "raw_registry__sources",
        "raw_registry__nynjtc_paper_maps",
    }
    for resource in reviewed:
        document = json.loads(resource.file.read_text())
        rows = 1 if resource.rows_key is None else len(document[resource.rows_key])
        assert counts[resource.table] == rows, resource.table


def test_a_folder_of_challenge_files_lands_one_verbatim_row_per_file(fixtures):
    """reference/challenges/<org>/ is a ReviewedDir: each file whole, `_README` aside, so the dbt gate reads JSON types."""
    root, counts = fixtures
    folders = [r for r in fixture_resources(root / "raw")[0] if isinstance(r, ReviewedDir)]
    assert {r.table for r in folders} >= {"raw_atc__challenges_atc"}
    for folder in folders:
        assert counts[folder.table] == len(folder.files), folder.table
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        rows = con.execute('select _path, row_json, _parse_error from raw."raw_atc__challenges_atc" order by _path').fetchall()
    on_disk = sorted((Path(make_dbt_fixtures.__file__).parent / "reference" / "challenges" / "atc").glob("*.json"))
    assert [path for path, _, _ in rows] == [str(p.relative_to(p.parents[3])) for p in on_disk]
    for (_, text, problem), path in zip(rows, on_disk, strict=True):
        written = json.loads(path.read_text(encoding="utf-8"))
        assert problem is None
        assert json.loads(text) == {name: value for name, value in written.items() if name != "_README"}


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
    """A proven-empty table (an empty layer, or a reviewed file with no rows) is made by _warehouse.py, not by dlt,
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


def test_a_return_z_layer_is_answered_as_esri_json_with_its_z_and_lands_with_it():
    """A row with `return_z` asks for f=json&returnZ=true; fixture mode answers as ArcGIS does, so the Z survives the pager."""
    from lib.arcgis import iter_layer_pages

    url = "https://services9.arcgis.com/fixture/arcgis/rest/services/Z/FeatureServer/9"
    line = {
        "type": "Feature",
        "properties": {"OBJECTID": 1},
        "geometry": {"type": "LineString", "coordinates": [[-68.9, 45.9, 1600.5], [-68.8, 45.8, 1590.0]]},
    }
    point = {"type": "Feature", "properties": {"OBJECTID": 2}, "geometry": {"type": "Point", "coordinates": [-91.4, 47.9, 457.7]}}
    session = requests.Session()
    session.mount("https://", FixtureAdapter({url: [line, point]}, {}, {}))

    with_z = [feature for page in iter_layer_pages(url, session=session, return_z=True) for feature in page]
    without = [feature for page in iter_layer_pages(url, session=session) for feature in page]

    assert [feature["geometry"] for feature in with_z] == [line["geometry"], point["geometry"]]
    assert [feature["properties"] for feature in with_z] == [{"OBJECTID": 1}, {"OBJECTID": 2}]
    assert without == [line, point], "the default path is answered exactly as before"


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
    # Every shelter the fixture writes lands, however many it writes: the
    # points_of_interest family's fixtures add ATC's real shelters from
    # reference/water_distance.json to the first three.
    written = json.loads((tmp_path / "data" / "raw" / "shelters.geojson").read_text())["features"]
    assert counts["raw_atc__shelters"] == len(written) > 3
