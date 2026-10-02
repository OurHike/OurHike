"""new_data_report.py: decision 31's review of what the marts carry that parity cannot check."""

import json

import duckdb
import pytest

import new_data_report
import parity

# A dispersed campsite, as USFS's CAMPING AREA rows look (export_nearby_poi.py's
# comment on USFS_SITE_TYPES): a forest-road name and a location that must
# never be published. The coordinates are written to be findable in any text.
DISPERSED = {"lat": 44.123456, "lon": -71.654321, "name": "RD 614 SITE 13"}
PERSON = {"photo_author": "Ada Person", "email": "ranger@example.org"}


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create schema marts")
    con.execute("create schema intermediate")
    con.execute(
        """
        create table marts.points_of_interest (
            club varchar, source_key varchar, source varchar, poi_type varchar, retired varchar,
            lat double, lon double, geom_geojson varchar, name varchar, photo_author varchar, "EMAIL" varchar
        )
        """
    )
    point = '{{"type":"Point","coordinates":[{lon},{lat}]}}'
    rows = [
        ("usfs", "usfs_rec_sites", "usfs_rec_sites", "campsite", None, DISPERSED["lat"], DISPERSED["lon"], DISPERSED["name"]),
        ("atc", "shelters", "atc_shelters", "shelter", None, 41.5, -74.5, "Fingerboard Shelter"),
        ("nycparks", "nyc_drinking_fountains", "nyc_drinking_fountains", "water", None, 40.7, -73.9, "Fountain"),
        ("ourhike", "poi_identity", "atc_csi", "water", "2026-08-19", 41.0, -74.0, "Retired spring"),
    ]
    for club, key, source, kind, retired, lat, lon, name in rows:
        con.execute(
            "insert into marts.points_of_interest values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                club,
                key,
                source,
                kind,
                retired,
                lat,
                lon,
                point.format(lon=lon, lat=lat),
                name,
                PERSON["photo_author"],
                PERSON["email"],
            ],
        )
    for table in ("closures_v1", "closures"):
        con.execute(f"create table marts.{table} (club varchar, source_key varchar, notice_kind varchar)")
        con.execute(f"insert into marts.{table} values ('ourhike', 'ourhike_closures', 'ourhike_closure')")
    con.execute("create table marts.warnings (club varchar, source_key varchar, warning_kind varchar)")
    con.execute("insert into marts.warnings values ('nws', 'nws_alerts', 'nws_alert')")
    con.execute(
        "create table marts.trail_lines (club varchar, source_key varchar, line_kind varchar, closure_kind varchar, closure_source varchar)"
    )
    con.execute("insert into marts.trail_lines values ('nysparks', 'oprhp_trails', 'network', 'area', 'oprhp_trail_closures')")
    con.execute(
        "create table marts.sources (source_key varchar, steward varchar, provider varchar, title varchar, kind varchar, reaches_hikers boolean)"
    )
    con.execute(
        "create table intermediate.int_sources__publication "
        "(source_key varchar, may_publish boolean, publication_rule varchar, licence_basis varchar)"
    )
    for key, may, rule, basis in (
        ("usfs_rec_sites", True, "registered_and_publishable", "stated_by_org"),
        ("shelters", True, "registered_and_publishable", "maintainer_authorisation"),
        ("nyc_drinking_fountains", True, "registered_and_publishable", "stated_by_org"),
        ("gatc_water_sources", False, "held_back_by_the_registry", "unresolved"),
    ):
        con.execute("insert into intermediate.int_sources__publication values (?, ?, ?, ?)", [key, may, rule, basis])
        con.execute(
            "insert into marts.sources values (?, 'A steward', 'provider', 'A layer', 'external_arcgis_layer', ?)", [key, may]
        )
    con.close()
    return path


@pytest.fixture
def parity_dir(tmp_path):
    folder = tmp_path / "parity"
    folder.mkdir()
    shelters = {
        "format": parity.RESULT_FORMAT,
        "family": "poi_shelter",
        "new_file_name": "poi_shelter.geojson",
        "old_sources": {"atc_shelters": 1},
        "old_records_naming_no_source": 0,
    }
    closures = {
        "format": parity.RESULT_FORMAT,
        "family": "closures",
        "new_file_name": "conditions_closures.json",
        "old_sources": {},
        "old_records_naming_no_source": 3,
    }
    for result in (shelters, closures):
        (folder / f"{result['family']}.json").write_text(json.dumps(result))
    return folder


def _written(out) -> str:
    return (out / "new_data_report.md").read_text() + (out / "new_data_report.json").read_text()


def test_the_report_holds_no_dispersed_campsite_location_and_no_person_field(warehouse, parity_dir, tmp_path):
    out = tmp_path / "out"
    assert new_data_report.main(["--warehouse", str(warehouse), "--parity-dir", str(parity_dir), "--out", str(out)]) == 0
    text = _written(out)
    for leaked in ("44.123456", "71.654321", DISPERSED["name"], PERSON["photo_author"], PERSON["email"], "EMAIL"):
        assert leaked not in text, leaked
    # The campsite is counted, which is what decision 31 asks of it.
    assert "| points_of_interest | usfs | campsite | 1 |" in text


def test_the_guard_refuses_a_person_field_and_a_location_wherever_they_sit():
    people = new_data_report.person_fields()
    with pytest.raises(ValueError, match="person field"):
        new_data_report.refuse_what_it_must_not_hold({"layers": [{"Supervisor": "x"}]}, people)
    with pytest.raises(ValueError, match="location"):
        new_data_report.refuse_what_it_must_not_hold({"rows": [{"lat": 44.1}]}, people)
    new_data_report.refuse_what_it_must_not_hold({"rows": [{"source_key": "dec_lean_tos", "rows": 2}]}, people)


def test_person_fields_reads_the_extract_s_own_denylist():
    from extract._kinds import PERSON_FIELDS

    assert new_data_report.person_fields() == PERSON_FIELDS


def test_a_source_today_s_files_never_named_lists_first_and_retired_rows_are_left_out(warehouse, parity_dir):
    report = new_data_report.build_report(warehouse, parity_dir)
    lines = [(row["line"], row["source_named_as"], row["today"]) for row in report["new_sources"]]
    assert lines == [
        ("closure", "ourhike_closures", "not_in_todays_compared_files"),
        ("closure", "oprhp_trail_closures", "not_in_todays_compared_files"),
        ("warning", "nws_alerts", "not_in_todays_compared_files"),
        ("water", "nyc_drinking_fountains", "not_in_todays_compared_files"),
        ("shelter", "atc_shelters", "published_today"),
    ]
    assert all(row["source_named_as"] != "atc_csi" for row in report["new_sources"]), "a retired tombstone is not a source"
    assert report["todays_files_naming_no_source"] == [{"family": "closures", "file": "conditions_closures.json", "records": 3}]


def test_a_mart_s_version_table_is_not_counted_beside_the_mart(warehouse, parity_dir):
    report = new_data_report.build_report(warehouse, parity_dir)
    closures = [row for row in report["mart_counts"] if row["mart"].startswith("closures")]
    assert [(row["mart"], row["rows"]) for row in closures] == [("closures", 1)]


def test_licence_basis_and_may_publish_come_from_int_sources__publication(warehouse, parity_dir):
    layers = {row["source_key"]: row for row in new_data_report.build_report(warehouse, parity_dir)["layers"]}
    assert (layers["gatc_water_sources"]["may_publish"], layers["gatc_water_sources"]["licence_basis"]) == (False, "unresolved")
    assert layers["shelters"]["rows_by_mart"] == {"points_of_interest": 1}


def test_without_parity_results_today_is_not_measured_rather_than_new(warehouse):
    report = new_data_report.build_report(warehouse, None)
    assert {row["today"] for row in report["new_sources"]} == {"not_measured"}


def test_a_warehouse_without_the_publication_model_exits_2(tmp_path):
    path = tmp_path / "empty.duckdb"
    duckdb.connect(str(path)).close()
    assert new_data_report.main(["--warehouse", str(path), "--out", str(tmp_path / "out")]) == 2
