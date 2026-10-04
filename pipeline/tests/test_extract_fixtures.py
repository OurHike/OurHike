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
from extract._contract import all_resources, discover, discover_shared
from extract._fixtures import (
    JSON_API_DIR,
    JSON_API_KINDS,
    NOTICES_DIR,
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
    FeedNotices,
    GuidePages,
    NwsAlerts,
    PageNotice,
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
        | PageNotice
        | FeedNotices
    )
    fetched = [r for r in resources if not isinstance(r, answered) and not isinstance(r, JSON_API_KINDS)]
    assert len(fetched) == 388, (
        "61 monthly layers and OPRHP's temporary closures on the hourly lane, and decision 53's 76 ArcGIS "
        "closure and warning layers: 70 hourly, 3 daily, 3 monthly, and decision 54's 83 places layers, all "
        "monthly, its 98 trail-line layers, all monthly, and its 69 point layers, all monthly"
    )
    for resource in fetched:
        expected = len(json.loads(fixture_file(root / "raw", resource.key).read_text())["features"])
        assert counts[resource.table] == expected, resource.table


#: The notice resources fixture mode leaves out: PDFs, which PageNotice reads through pypdf, and the pipeline and dbt
#: jobs install no pypdf (make_dbt_fixtures.py's notice comment).
NOTICE_PDFS = {"bmta_alerts_pdf", "foot_hiker_alert_mm195", "tatc_ridgerunner_reports", "trustees_hunting_designations"}


def test_every_notice_page_and_feed_lands_the_rows_its_answers_make_and_each_page_row_a_title(fixtures):
    """Decision 53 phase B: each PageNotice and FeedNotices resource with a conditions/notices/ file lands exactly
    the file's `rows` (one a page, one an item for a feed), and a page's row carries a title, so a page whose region
    or title the reader cannot find fails here rather than in a live run. The four PDFs are the only notice
    resources with no file."""
    root, counts = fixtures
    resources, _ = fixture_resources(root / "raw")
    notices = [r for r in resources if isinstance(r, FeedNotices | PageNotice)]
    registered = {r.key for r in all_resources(discover() + discover_shared()) if isinstance(r, FeedNotices | PageNotice)}
    files = sorted((root / "raw" / "conditions" / NOTICES_DIR).glob("*.json"))
    assert {r.key for r in notices} == {path.stem for path in files}
    assert registered - {r.key for r in notices} == NOTICE_PDFS
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        for resource in notices:
            expected = json.loads((root / "raw" / "conditions" / NOTICES_DIR / f"{resource.key}.json").read_text())["rows"]
            assert counts[resource.table] == expected, resource.table
            if isinstance(resource, PageNotice):
                (title,) = con.execute(f'select title from raw."{resource.table}"').fetchone()
                assert title, resource.table


def test_a_wordpress_rows_person_fields_never_reach_the_raw_store(fixtures):
    """Decision 59: OHTA's, TEHCC's, TKO's and PNTA's post bodies carried telephone numbers and an e-mail address on
    2026-10-03, so their rows list `content` and `excerpt` as person_fields, and the table lands without them."""
    root, counts = fixtures
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        for table in (
            "raw_ohta__ohta_trail_alerts_posts",
            "raw_tehcc__tehcc_at_posts",
            "raw_tko__tko_oct_trail_conditions",
            "raw_pnta__pnta_trail_conditions_posts",
        ):
            assert counts[table] == 2, table
            columns = {row[0] for row in con.execute(f'describe raw."{table}"').fetchall()}
            assert not {name for name in columns if name.startswith(("content", "excerpt"))}, (table, sorted(columns))
            assert "title__rendered" in columns or "title" in columns, (table, sorted(columns))


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
    # Section C's content feeds and APIs (decision 54 wave 3, 2026-10-04): each podcast feed's two fixture
    # episodes (make_dbt_fixtures.py's _podcast_feed), TEHCC's template pages and NPS's five lists, two rows each.
    "raw_nysdec__dec_does_what_podcast": 2,
    "raw_mohonk__mohonk_walk_back_in_time_podcast": 2,
    "raw_nycparks__nycparks_covid_oral_history_podcast": 2,
    "raw_njgin__njdep_discover_dep_podcast": 2,
    "raw_usfs__usfs_forest_focus_podcast": 2,
    "raw_usfs__usfs_forestcast_podcast": 2,
    "raw_blm__blm_on_the_ground_podcast": 2,
    "raw_cotrex__cpw_colorado_outdoors_podcast": 2,
    "raw_wi_dnr__wdnr_wild_wisconsin_podcast": 2,
    "raw_wi_dnr__silvicast_podcast": 2,
    "raw_amc__amc_unlikely_stories_podcast": 2,
    "raw_spnhf__something_wild_podcast": 2,
    "raw_trustees__trustees_on_the_coast_podcast": 2,
    "raw_sbts__sbts_dirt_magic_podcast": 2,
    "raw_smd__audible_mount_diablo_podcast": 2,
    "raw_shta__shta_blazing_trail_podcast": 2,
    "raw_usgs_tnm__usgs_outstanding_in_the_field_podcast": 2,
    "raw_nps__nps_park_postcards_goga_podcast": 2,
    "raw_usfws__usfws_future_of_conservation_podcast": 2,
    "raw_tehcc__tehcc_wiki_trails": 2,
    "raw_tehcc__tehcc_wiki_hikes": 2,
    "raw_tehcc__tehcc_wiki_challenge_items": 1,
    "raw_nps__nps_multimedia_audio": 2,
    "raw_nps__nps_gallery_assets": 2,
    "raw_nps__nps_passport_stamp_locations": 2,
    "raw_nps__nps_things_to_do": 2,
    "raw_nps__nps_tours": 2,
}


def test_the_json_api_notice_sources_land_from_their_answers_with_no_nps_key_in_the_environment(fixtures):
    """Every extract/_json_apis.py resource answered from conditions/json_apis/, NPS's two under fixture mode's placeholder key."""
    root, counts = fixtures
    resources, _ = fixture_resources(root / "raw")
    # extract/_gis_files.py's and extract/_ogc.py's kinds ride the same answers folder; GIS_AND_GEO_API_ROWS holds them.
    # Section C's content readers (extract/_content.py) are JSON_API_ROWS' too.
    landed = {r.table for r in resources if isinstance(r, JSON_API_KINDS) and type(r).__module__ not in GIS_AND_GEO_MODULES}
    assert landed == set(JSON_API_ROWS)
    assert all((root / "raw" / "conditions" / JSON_API_DIR / f"{r.key}.json").exists() for r in resources if r.table in landed)
    assert {table: counts[table] for table in JSON_API_ROWS} == JSON_API_ROWS


def test_section_cs_content_lands_no_author_or_guest_and_none_of_the_prose_a_row_names_as_personal(fixtures):
    """Decision 59 at the warehouse, for decision 54 wave 3's content: no episode's author, creator or guest tag lands
    on any feed; the fixture number in an episode's notes and a hike page's body (555-0100) lands only where the row's
    `person_fields` do not name that prose; NPS's audio transcripts land nowhere."""
    root, _ = fixtures
    feeds = [table for table in JSON_API_ROWS if table.endswith("_podcast")]
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:

        def columns(table: str) -> set[str]:
            return {row[0] for row in con.execute(f"describe raw.{table}").fetchall()}

        def values(table: str) -> str:
            return json.dumps(con.execute(f"select * from raw.{table}").fetchall(), default=str)

        for table in feeds:
            assert not [c for c in columns(table) if "author" in c or "creator" in c or "person" in c], table
            landed = values(table)
            assert not [name for name in ("Fixture Person", "Fixture Guest", "fixture.person@") if name in landed], table
        assert "555-0100" not in values("raw_njgin__njdep_discover_dep_podcast"), "NJDEP's notes name its staff"
        assert "555-0100" in values("raw_nysdec__dec_does_what_podcast"), "a row naming no prose keeps its notes in raw"
        assert not {"content", "excerpt"} & columns("raw_nmvfo__nmvfo_hike_new_mexico")
        assert "555-0100" not in values("raw_nmvfo__nmvfo_hike_new_mexico"), "NMVFO's pages carry volunteers' numbers"
        assert "Fixture Person" not in values("raw_gmc__gmc_hikes"), "Spectra's and Yoast's author blocks never load"
        assert "transcript" not in columns("raw_nps__nps_multimedia_audio")


# Decision 54's waves 2 and 3 (section G, 2026-10-04): each GIS file and geographic API, the rows its fixture answers
# hold (make_dbt_fixtures.py's _gis_file_documents() and _geo_api_documents()). Catamount's main trail lands 3 rows
# with 2 exact copies among them, a KMZ and a zipped GPX arrive whole as ASCII-only zips, and a location with no
# coordinate lands with no geometry rather than being dropped. FMST's sheet opens with a title line
# above its header and a row of empty cells between sections, so it lands 2 rows from 3 lines of data.
#: The modules section G's kinds live in, which is what separates its tables from JSON_API_ROWS': both ride
#: extract/_fixtures.py's JSON_API_KINDS and the same answers folder.
GIS_AND_GEO_MODULES = frozenset({"extract._gis_files", "extract._ogc"})
GIS_AND_GEO_API_ROWS = {
    "raw_nez_perce__usfs_nez_perce_nht_my_map": 4,
    "raw_rmfi__rmfi_project_map": 2,
    "raw_fpc__fpc_forest_park_trailheads": 1,
    "raw_ota__ota_trail_map": 3,
    "raw_bartram__bartram_trail_markers_map": 2,
    "raw_bartram__bartram_trail_map": 3,
    "raw_bmecc__bmecc_trail_section_map": 4,
    "raw_ohta__ohta_website_track": 1,
    "raw_pohe__phta_trails_map": 3,
    "raw_nbatc__nbatc_trails": 1,
    "raw_nbatc__nbatc_trail_features": 2,
    "raw_nbatc__nbatc_shelters": 1,
    "raw_nbatc__nbatc_trail_info": 1,
    "raw_catamount__catamount_main_trail": 3,
    "raw_catamount__catamount_side_trails": 1,
    "raw_catamount__catamount_full_route": 2,
    "raw_catamount__catamount_sections": 2,
    "raw_catamount__catamount_access_points": 2,
    "raw_catamount__catamount_businesses": 1,
    "raw_catamount__catamount_backcountry_zones": 1,
    "raw_fmst__fmst_primary_trailheads": 2,
    "raw_hoosier__hhc_tecumseh_waypoints": 2,
    "raw_hoosier__hhc_tecumseh_track": 1,
    "raw_condor__condor_trail_2020": 4,
    "raw_nc_high_peaks__nchpta_trails": 1,
    "raw_mdhta__mdhta_trail_guide": 19,
    "raw_ocvt__ocvt_at_tracks": 2,
    "raw_mtsg__mtsg_map_locations": 3,
    "raw_nps__nps_api_places": 2,
    "raw_nps__nps_api_campgrounds": 2,
}


def test_every_gis_file_and_geographic_api_lands_from_its_answers_and_no_person_field_arrives(fixtures):
    """Section G's resources, answered from conditions/json_apis/: every one lands, at its fixture's row count."""
    root, counts = fixtures
    resources, _ = fixture_resources(root / "raw")
    landed = {r.table for r in resources if isinstance(r, JSON_API_KINDS) and type(r).__module__ in GIS_AND_GEO_MODULES}
    assert landed == set(GIS_AND_GEO_API_ROWS)
    assert {table: counts[table] for table in GIS_AND_GEO_API_ROWS} == GIS_AND_GEO_API_ROWS
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        places = {row[0] for row in con.execute("describe raw.raw_nps__nps_api_places").fetchall()}
        values = json.dumps(con.execute("select * from raw.raw_nps__nps_api_places").fetchall(), default=str)
        missing = con.execute("select count(*) from raw.raw_mtsg__mtsg_map_locations where geometry is null").fetchone()[0]
    assert "images" not in places and "Fixture Photographer" not in values, "a photographer's credit never loads"
    assert missing == 1


def test_a_notice_feed_lands_no_creator_and_no_prose_and_a_page_lands_its_own_title_and_date(fixtures):
    """Decision 55 and rule 8 at the warehouse: the fixture feed's `dc:creator` and `description` arrive nowhere."""
    root, _ = fixtures
    with duckdb.connect(str(root / "warehouse.duckdb"), read_only=True) as con:
        feed = {row[0] for row in con.execute("describe raw.raw_cvatc__cvatc_news").fetchall()}
        values = json.dumps(con.execute("select * from raw.raw_cvatc__cvatc_news").fetchall(), default=str)
        page = con.execute("select title, date, date_source from raw.raw_msgtc__msgtc_trail_conditions").fetchone()
    assert not {"description", "creator", "dc_creator", "content"} & feed
    assert "Fixture Person" not in values and "Fixture prose" not in values
    assert page[1:] == ("2026-09-21", "wp_modified") and page[0].startswith("Fixture Notice Page")


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


def test_a_page_query_sent_as_a_post_form_is_paged_by_its_form():
    """A layer that names 150 fields pages past GET_URL_LIMIT, so query_page() POSTs; fixture mode reads the form.

    Found when PA DCNR's state park buildings (120-odd fields, decision 54's points of interest) failed
    fixture mode with "it ignores resultOffset": every POSTed page was answered as offset 0.
    """
    from lib.arcgis import GET_URL_LIMIT, iter_layer_pages

    url = "https://services9.arcgis.com/fixture/arcgis/rest/services/Wide/FeatureServer/0"
    fields = [f"INSURED_REPLACEMENT_VALUE_{n:03d}" for n in range(150)]
    features = [
        {
            "type": "Feature",
            "properties": {"OBJECTID": n, **dict.fromkeys(fields)},
            "geometry": {"type": "Point", "coordinates": [-77.5, 40.5]},
        }
        for n in (1, 2, 3)
    ]
    session = requests.Session()
    session.mount("https://", FixtureAdapter({url: features}, {}, {}))
    out_fields = ",".join(["OBJECTID", *fields])
    get_url = requests.Request("GET", url + "/query", params={"outFields": out_fields}).prepare().url
    assert len(get_url) > GET_URL_LIMIT, "the case needs a query that goes as a POST"

    pages = list(iter_layer_pages(url, session=session, out_fields=out_fields, page_size=1))

    assert [feature["properties"]["OBJECTID"] for page in pages for feature in page] == [1, 2, 3]


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
