"""extract/_gis_files.py and extract/_ogc.py, decision 54's waves 2 and 3, against mocked servers.

Each reader is asked for its rows directly, or run through the hourly lane into
a `file://` raw store under tmp_path where dlt and the warehouse are the
question. requests_mock answers as each kind of upstream did when section G's
live reads were made on 2026-10-04; every body is invented and shaped like
those answers. conftest.py's socket guard stays on.

The cases are the ones a file or an API has been measured to get wrong, or
that a hiker's safety turns on: an HTML page served where a KML was, a file in
projected coordinates, a NetworkLink nobody follows, a KML with an undeclared
prefix (NBATC's), exact copies inside one file (Catamount's), a change check
that must not say FRESH when any one file moved or sent no validator, an OGC
server that repeats a page, a JSON API whose key is not set, and person fields
that never reach a row.
"""

import io
import json
import struct
import zipfile

import pytest

from extract import _gis_files, _kinds, _notices, _ogc
from extract._contract import Unavailable
from extract._gis_files import GisFile, GisFileUnreadable, gis_file, parse_geojson, parse_gpx, parse_kml, parse_shapefile_zip
from extract._ogc import JsonFeatures, OgcFeatures, json_features
from lib import http_retry
from lib.freshness_state import Freshness
from tests.test_extract_run import lane, warehouse

KML_URL = "https://maps.example.com/maps/d/kml?mid=abc&forcekml=1"
KMZ_URL = "https://club.example.org/MapData/features.kmz"
GPX_URL = "https://club.example.org/assets/waypoints.gpx"
GEOJSON_A = "https://club.example.org/data/a.geojson"
GEOJSON_B = "https://club.example.org/data/b.geojson"
SHP_URL = "https://club.example.org/data/points.zip"
CSV_URL = "https://club.example.org/data/access.csv"
SHEET_URL = "https://docs.example.org/spreadsheets/d/fixture/export?format=csv"
OGC_URL = "https://ogc.example.org/collections/trails/items"
WP_URL = "https://club.example.org/wp-json/wp/v2/cm-map-location"
NPS_URL = "https://nps.example.gov/api/v1/places"
VENUES_URL = "https://club.example.org/wp-json/tribe/events/v1/venues"


def kml(*placemarks: str, folder: str = "Fixture Folder", extra: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Fixture</name>'
        f"<Folder><name>{folder}</name>{''.join(placemarks)}</Folder>{extra}</Document></kml>"
    )


def placemark(name: str, coordinates: str, shape: str = "Point", data: dict | None = None) -> str:
    extended = ""
    if data:
        extended = (
            "<ExtendedData>" + "".join(f'<Data name="{k}"><value>{v}</value></Data>' for k, v in data.items()) + "</ExtendedData>"
        )
    return f"<Placemark><name>{name}</name>{extended}<{shape}><coordinates>{coordinates}</coordinates></{shape}></Placemark>"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding one entry per reader, in place of the real one."""
    path = tmp_path / "sources.json"
    sources = [
        {"key": "my_map", "url": KML_URL, "file_format": "kml"},
        {"key": "features_kmz", "url": KMZ_URL, "file_format": "kmz"},
        {"key": "waypoints", "url": GPX_URL, "file_format": "gpx"},
        {"key": "two_files", "url": "https://club.example.org/data/", "files": [GEOJSON_A, GEOJSON_B], "file_format": "geojson"},
        {"key": "access_csv", "url": CSV_URL, "file_format": "csv_points", "lat_field": "LATITUDE", "lon_field": "LONGITUDE"},
        {
            "key": "trailhead_sheet",
            "url": SHEET_URL,
            "file_format": "csv_points",
            "header_row": 2,
            "as_of_label": "Current as of:",
            "lat_field": "Latitude",
            "lon_field": "Longitude",
        },
        {"key": "staffed_map", "url": KML_URL, "file_format": "kml", "person_fields": ["Leader"]},
        {"key": "ogc_trails", "url": OGC_URL},
        {
            "key": "map_locations",
            "url": WP_URL,
            "paging": "wordpress",
            "page_size": 2,
            "params": {"_latlng": "acf_loc_address"},
            "lat_field": "location.lat",
            "lon_field": "location.lng",
            "id_field": "id",
            "modified_field": "modified_gmt",
        },
        {
            "key": "nps_places",
            "url": NPS_URL,
            "paging": "start_limit",
            "page_size": 2,
            "items_field": "data",
            "total_field": "total",
            "lat_field": "latitude",
            "lon_field": "longitude",
            "api_key_env": "FIXTURE_TEST_API_KEY",
            "person_fields": ["images"],
            "key_fields": ["id"],
        },
        {
            "key": "venues",
            "url": VENUES_URL,
            "paging": "next_url",
            "items_field": "venues",
            "next_url_field": "next_rest_url",
            "total_field": "total",
            "lat_field": "geo_lat",
            "lon_field": "geo_lng",
        },
    ]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """No host is asked anything, so the per-host gate and the retry ladder never sleep."""
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)


@pytest.fixture
def store(tmp_path):
    """A `file://` raw store and a dlt working directory under tmp_path, as tests/test_extract_run.py's."""
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


def gis(key: str, type_: str = "points_of_interest") -> GisFile:
    return GisFile(key=key, club="testclub", type=type_)


# --- parsing ---------------------------------------------------------------------


def test_a_kml_placemark_lands_its_folder_its_own_columns_and_extended_data_as_text():
    rows, links = parse_kml(
        kml(
            placemark("Fixture Spring", "-74.0,41.0,0", data={"Type": "Spring", "Name": "Fixture Spring", "Latitude": "41.0"}),
            placemark("Fixture Line", "-74.0,41.0 -74.0,41.1", shape="LineString"),
            folder="Springs",
            extra="<NetworkLink><name>elsewhere</name></NetworkLink>",
        ).encode(),
        KML_URL,
    )

    assert links == 1, "a NetworkLink is counted and never followed"
    spring, line = rows
    assert (spring["folder"], spring["name"], spring["Type"], spring["Latitude"]) == (
        "Springs",
        "Fixture Spring",
        "Spring",
        "41.0",
    )
    assert spring["property_Name"] == "Fixture Spring", "a data name that collides with the placemark's own lands prefixed"
    assert spring["geometry"] == {"type": "Point", "coordinates": [-74.0, 41.0, 0.0]}
    assert line["geometry"]["type"] == "LineString"
    assert (spring["feature_index"], line["feature_index"]) == (0, 1)


def test_a_kml_that_uses_a_prefix_it_never_declares_still_parses():
    # NBATC_Trails_015.kml puts xsi:schemaLocation on its <Document> with no xmlns:xsi (read 2026-10-04).
    body = kml(placemark("Fixture Trail", "-74.0,41.0 -74.0,41.1", shape="LineString")).replace(
        "<Document>", '<Document xsi:schemaLocation="http://earth.google.com/kml/2.1 kml21.xsd">'
    )

    rows, _ = parse_kml(body.encode(), KML_URL)

    assert [row["name"] for row in rows] == ["Fixture Trail"]


def test_an_html_page_served_where_a_kml_was_is_refused_not_read_as_an_empty_file():
    with pytest.raises(GisFileUnreadable):
        parse_kml(b"<!DOCTYPE html><html><head><title>Moved</title></head><body>gone</body></html>", KML_URL)


def test_a_gpx_waypoint_keeps_its_elevation_as_z_and_a_one_point_track_segment_is_dropped():
    body = (
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">'
        '<wpt lat="41.0" lon="-74.0"><ele>312.5</ele><name>Fixture_Shelter</name><sym>RED MAP PIN</sym></wpt>'
        '<trk><name>Fixture Track</name><trkseg><trkpt lat="41.0" lon="-74.0"/><trkpt lat="41.1" lon="-74.0"/></trkseg>'
        '<trkseg><trkpt lat="41.2" lon="-74.0"/></trkseg></trk></gpx>'
    )

    waypoint, track = parse_gpx(body.encode(), GPX_URL)

    assert (waypoint["feature_kind"], waypoint["name"], waypoint["sym"], waypoint["ele"]) == (
        "waypoint",
        "Fixture_Shelter",
        "RED MAP PIN",
        "312.5",
    )
    assert waypoint["geometry"] == {"type": "Point", "coordinates": [-74.0, 41.0, 312.5]}
    assert track["geometry"] == {"type": "LineString", "coordinates": [[-74.0, 41.0], [-74.0, 41.1]]}


def test_a_lone_geojson_feature_is_one_row_and_every_property_lands_as_text():
    body = json.dumps(
        {
            "type": "Feature",
            "id": 7,
            "properties": {"name": "Track 040", "length": 1.5, "tags": ["a"]},
            "geometry": {"type": "LineString", "coordinates": [[-74.0, 41.0, 774.4], [-74.0, 41.1, 780.0]]},
        }
    )

    (row,) = parse_geojson(body.encode(), GEOJSON_A)

    assert (row["feature_id"], row["name"], row["length"], row["tags"]) == ("7", "Track 040", "1.5", '["a"]')
    assert row["geometry"]["coordinates"][0] == [-74.0, 41.0, 774.4], "the Z an elevation row reads is kept"


@pytest.mark.parametrize(
    "document",
    [
        {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::26918"}},
            "features": [],
        },
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [583000.0, 4540000.0]}}
            ],
        },
    ],
    ids=["a projected crs member", "projected coordinates with no crs member"],
)
def test_a_geojson_file_in_projected_coordinates_is_refused_rather_than_landed_in_the_ocean(document):
    with pytest.raises(GisFileUnreadable):
        parse_geojson(json.dumps(document).encode(), GEOJSON_A)


def shapefile_zip(prj: str | None) -> bytes:
    """A zipped point shapefile: two records, a dBASE table with one text column, written by hand to the 1998 spec."""
    records = b""
    for number, (x, y) in enumerate(((-74.0, 41.0), (-73.9, 41.1)), start=1):
        content = struct.pack("<i2d", 1, x, y)
        records += struct.pack(">2i", number, len(content) // 2) + content
    header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(records)) // 2) + struct.pack(
        "<2i4d4d", 1000, 1, -74.0, 41.0, -73.9, 41.1, 0, 0, 0, 0
    )
    field = b"NAME".ljust(11, b"\x00") + b"C" + b"\x00" * 4 + bytes([20, 0]) + b"\x00" * 14
    dbf = struct.pack("<BBBBIHH20x", 3, 126, 1, 1, 2, 32 + 32 + 1, 1 + 20) + field + b"\x0d"
    dbf += b" " + b"Fixture One".ljust(20) + b" " + b"Fixture Two".ljust(20) + b"\x1a"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("points.shp", header + records)
        archive.writestr("points.dbf", dbf)
        if prj is not None:
            archive.writestr("points.prj", prj)
        archive.writestr("__MACOSX/._points.shp", b"resource fork")
    return buffer.getvalue()


def test_a_zipped_shapefile_reads_its_points_and_its_dbf_columns_with_nothing_the_extract_does_not_pin():
    rows = parse_shapefile_zip(shapefile_zip('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984"]]'), SHP_URL)

    assert [row["NAME"] for row in rows] == ["Fixture One", "Fixture Two"]
    assert rows[1]["geometry"] == {"type": "Point", "coordinates": [-73.9, 41.1]}
    assert rows[0]["source_file"] == f"{SHP_URL}#points.shp"


def test_a_zipped_shapefile_whose_prj_is_projected_is_refused():
    with pytest.raises(GisFileUnreadable, match="not geographic"):
        parse_shapefile_zip(shapefile_zip('PROJCS["NAD_1983_UTM_Zone_18N",GEOGCS["GCS_North_American_1983"]]'), SHP_URL)


# --- the resource: reading, the proof, person fields ----------------------------


def test_a_kmz_unzips_in_memory_and_its_rows_count_as_their_own_exact_proof(registry, requests_mock):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "doc.kml", kml(placemark("Fixture Bridge", "-74.0,41.0,0"), placemark("Fixture Parking", "-74.1,41.0,0"))
        )
    requests_mock.get(KMZ_URL, content=buffer.getvalue(), headers={"Content-Type": "application/vnd.google-earth.kmz"})
    resource = gis("features_kmz")

    proofs = {}
    rows = list(resource.rows(proofs))

    assert [row["name"] for row in rows] == ["Fixture Bridge", "Fixture Parking"]
    assert rows[0]["source_file"] == f"{KMZ_URL}#doc.kml"
    assert proofs == {"raw_testclub__features_kmz": 2}
    assert resource.exact_proof


def test_every_file_of_a_dataset_is_read_and_each_row_says_which_file_it_came_from(registry, requests_mock):
    for url, name in ((GEOJSON_A, "Fixture A"), (GEOJSON_B, "Fixture B")):
        requests_mock.get(
            url,
            text=json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"name": name},
                            "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]},
                        }
                    ],
                }
            ),
        )

    rows = list(gis("two_files", "trail_lines").rows({}))

    assert [(row["source_file"], row["name"]) for row in rows] == [(GEOJSON_A, "Fixture A"), (GEOJSON_B, "Fixture B")]


def test_a_csv_row_whose_coordinate_is_not_a_number_lands_with_no_geometry_rather_than_a_guess(registry, requests_mock):
    requests_mock.get(CSV_URL, text="LOCATION,LONGITUDE,LATITUDE,PRIMARY\nFixture Road,-74.0,41.0,Yes\nFixture Gap,,unknown,No\n")

    road, gap = gis("access_csv").rows({})

    assert road["geometry"] == {"type": "Point", "coordinates": [-74.0, 41.0]}
    assert gap["geometry"] is None
    assert gap["PRIMARY"] == "No"


def test_a_person_field_named_on_the_row_or_shaped_like_one_never_reaches_a_row(registry, requests_mock):
    body = kml(
        placemark("Fixture Hike", "-74.0,41.0,0", data={"Leader": "Fixture Person", "Contact_Phone": "555-0100", "Type": "Hike"})
    )
    requests_mock.get(KML_URL, text=body, headers={"Content-Type": "text/xml; charset=utf-8"})

    (row,) = gis("staffed_map").rows({})

    assert row["Type"] == "Hike"
    assert "Leader" not in row, "the row's person_fields"
    assert "Contact_Phone" not in row, "PERSON_SHAPED"


def test_a_wall_answered_where_the_file_was_raises_and_lands_nothing(registry, requests_mock):
    requests_mock.get(KML_URL, status_code=403, text="Forbidden")

    with pytest.raises(Exception):
        list(gis("my_map").rows({}))


# --- the change check, per file -----------------------------------------------------


def test_the_change_check_is_fresh_only_when_every_file_keeps_its_own_validator(registry, requests_mock):
    requests_mock.head(GEOJSON_A, headers={"ETag": '"a1"'})
    requests_mock.head(GEOJSON_B, headers={"Last-Modified": "Mon, 27 Nov 2017 16:35:34 GMT", "Content-Length": "803294"})
    resource = gis("two_files", "trail_lines")

    first, marker = resource.change_check(None)
    again, _ = resource.change_check(marker)
    requests_mock.head(GEOJSON_B, headers={"Last-Modified": "Mon, 27 Nov 2017 16:35:34 GMT", "Content-Length": "803295"})
    moved, _ = resource.change_check(marker)

    assert (first, again, moved) == (Freshness.STALE, Freshness.FRESH, Freshness.STALE)
    assert marker == {
        "files": {
            GEOJSON_A: {"etag": '"a1"'},
            GEOJSON_B: {"last_modified": "Mon, 27 Nov 2017 16:35:34 GMT", "content_length": "803294"},
        }
    }


def test_a_file_that_sends_no_validator_makes_the_whole_check_unknown_never_fresh(registry, requests_mock):
    # Google My Maps sends no ETag and no Last-Modified (measured 2026-10-04 on 9 exports).
    requests_mock.head(GEOJSON_A, headers={"ETag": '"a1"'})
    requests_mock.head(GEOJSON_B, headers={"Cache-Control": "no-store"})

    verdict, marker = gis("two_files", "trail_lines").change_check({"files": {GEOJSON_A: {"etag": '"a1"'}}})

    assert (verdict, marker) == (Freshness.UNKNOWN, None)


def test_a_head_the_host_refuses_is_unknown_and_the_file_is_read(registry, requests_mock):
    requests_mock.head(GPX_URL, status_code=405)

    assert gis("waypoints").change_check(None) == (Freshness.UNKNOWN, None)


def test_a_sheet_whose_header_sits_under_a_title_line_keeps_both_ends_of_a_segment_and_skips_its_spacing(registry, requests_mock):
    # Shaped like FMST's "Primary Trailheads" export (2026-10-04): a title line, then a header that names
    # Latitude and Longitude twice, once per end of a segment, and rows of empty cells between sections.
    requests_mock.get(
        SHEET_URL,
        text=(
            '"Fixture sheet, use as you like",,,Current as of:,1/1/2026,,,\n'
            "Segment,Trailhead 1,Latitude,Longitude,,Trailhead 2,Latitude,Longitude\n"
            "1,Fixture Gap Trailhead,35.5,-83.5,,Fixture Knob Overlook,35.6,-83.4\n"
            ",,,,,,,\n"
            "2,Fixture Knob Overlook,35.6,-83.4,,,,\n"
        ),
    )

    gap, knob = gis("trailhead_sheet").rows({})

    assert gap["Trailhead 1"] == "Fixture Gap Trailhead"
    assert gap["geometry"] == {"type": "Point", "coordinates": [-83.5, 35.5]}
    assert (gap["property_Latitude"], gap["property_Longitude"]) == ("35.6", "-83.4")
    assert knob["feature_index"] == 2
    assert knob["geometry"] == {"type": "Point", "coordinates": [-83.4, 35.6]}
    assert knob["property_Latitude"] is None
    # The sheet's own date, from the cell after its as_of_label above the header (decision 72).
    assert (gap["source_as_of"], knob["source_as_of"]) == ("1/1/2026", "1/1/2026")


@pytest.mark.parametrize(
    "title_line",
    [
        pytest.param('"Fixture sheet, use as you like",,,,,,,\n', id="the label has gone"),
        pytest.param('"Fixture sheet, use as you like",,,Current as of:,,,,\n', id="the date beside it has gone"),
    ],
)
def test_a_sheet_whose_as_of_cell_has_gone_is_unreadable_rather_than_landed_undated(registry, requests_mock, title_line):
    requests_mock.get(
        SHEET_URL,
        text=title_line
        + "Segment,Trailhead 1,Latitude,Longitude,,Trailhead 2,Latitude,Longitude\n1,Fixture Gap,35.5,-83.5,,,,\n",
    )

    with pytest.raises(GisFileUnreadable, match="Current as of:"):
        list(gis("trailhead_sheet").rows({}))


def test_an_as_of_label_on_a_csv_whose_header_is_its_first_line_is_refused_at_import(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    entry = {"key": "bad", "url": CSV_URL, "file_format": "csv_points", "lat_field": "LATITUDE", "lon_field": "LONGITUDE"}
    path.write_text(json.dumps({"sources": [{**entry, "as_of_label": "Current as of:"}]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()

    with pytest.raises(KeyError, match="as_of_label"):
        gis_file("bad")
    _kinds._registry.cache_clear()


def test_a_csv_row_whose_header_row_is_not_a_line_number_is_refused_at_import(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    entry = {"key": "bad", "url": CSV_URL, "file_format": "csv_points", "lat_field": "LATITUDE", "lon_field": "LONGITUDE"}
    path.write_text(json.dumps({"sources": [{**entry, "header_row": 0}]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()

    with pytest.raises(KeyError, match="header_row"):
        gis_file("bad")
    _kinds._registry.cache_clear()


def test_a_gis_file_row_without_a_known_format_is_refused_at_import(registry, tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"sources": [{"key": "bad", "url": GPX_URL, "file_format": "dwg"}]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()

    with pytest.raises(KeyError, match="file_format"):
        gis_file("bad")


# --- through dlt and the warehouse --------------------------------------------------


def test_a_gis_file_lands_through_the_lane_and_its_geometry_round_trips_into_a_real_geometry(registry, store, requests_mock):
    requests_mock.head(KML_URL, headers={"Cache-Control": "no-store"})
    requests_mock.get(
        KML_URL,
        text=kml(placemark("Fixture Spring", "-74.0,42.0", data={"Type": "Spring"}), placemark("Fixture Shelter", "-74.1,42.0")),
        headers={"Content-Type": "text/xml; charset=utf-8"},
    )
    resource = GisFile(
        key="my_map", club="testclub", type="points_of_interest", cadence_override="hourly", cadence_reason="a test"
    )

    report = lane(store, resource)

    assert report.outcome == "loaded"
    assert report.rows == {"raw_testclub__my_map": 2}
    con, counts = warehouse(store)
    assert counts == {"raw_testclub__my_map": 2}
    con.execute("INSTALL spatial; LOAD spatial;")
    (point,) = con.execute(
        "select st_astext(st_geomfromgeojson(geometry::varchar)) from raw.raw_testclub__my_map where name = 'Fixture Spring'"
    ).fetchone()
    assert point == "POINT (-74 42)"


# --- OGC API Features ---------------------------------------------------------------


def ogc_page(ids: list[int], following: str | None, matched: int | None = 3) -> dict:
    page = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": i,
                "properties": {"name": f"Fixture {i}"},
                "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]},
            }
            for i in ids
        ],
        "links": [{"rel": "next", "href": following}] if following else [],
    }
    if matched is not None:
        page["numberMatched"] = matched
    return page


def test_an_ogc_collection_is_paged_by_the_next_link_the_server_gives_and_held_to_number_matched(registry, requests_mock):
    requests_mock.get(OGC_URL, [{"json": ogc_page([1, 2], "items?cursor=xyz")}])
    requests_mock.get("https://ogc.example.org/collections/trails/items?cursor=xyz", json=ogc_page([3], None))
    resource = OgcFeatures(key="ogc_trails", club="testclub", type="trail_lines")

    proofs = {}
    rows = list(resource.rows(proofs))

    assert [row["feature_id"] for row in rows] == ["1", "2", "3"]
    assert proofs == {"raw_testclub__ogc_trails": 3}
    assert resource.change_check(None) == (Freshness.UNKNOWN, None), "no collection-wide validator, so every run reads it"


def test_an_ogc_server_whose_next_link_repeats_a_page_is_refused_rather_than_read_forever(registry, requests_mock):
    requests_mock.get(OGC_URL, json=ogc_page([1], "https://ogc.example.org/collections/trails/items?page=2"))
    requests_mock.get(
        "https://ogc.example.org/collections/trails/items?page=2",
        json=ogc_page([2], "https://ogc.example.org/collections/trails/items?page=2"),
    )

    with pytest.raises(RuntimeError, match="repeats a page"):
        list(OgcFeatures(key="ogc_trails", club="testclub", type="trail_lines").rows({}))


def test_an_ogc_read_shorter_than_number_matched_raises(registry, requests_mock):
    requests_mock.get(OGC_URL, json=ogc_page([1, 2], None, matched=5))

    with pytest.raises(RuntimeError, match="matches 5"):
        list(OgcFeatures(key="ogc_trails", club="testclub", type="trail_lines").rows({}))


# --- JSON APIs with a coordinate ----------------------------------------------------


def location(n: int, lat=41.0, lng=-74.0) -> dict:
    return {
        "id": n,
        "modified_gmt": "2026-09-21T14:13:20",
        "title": {"rendered": f"Fixture {n}"},
        "location": {"lat": lat, "lng": lng} if lat is not None else None,
        "author": 84,
    }


def test_a_wordpress_route_is_paged_to_its_total_and_an_item_without_a_coordinate_gets_no_geometry(registry, requests_mock):
    headers = {"X-WP-Total": "3", "X-WP-TotalPages": "2"}
    requests_mock.get(
        WP_URL, [{"json": [location(1), location(2)], "headers": headers}, {"json": [location(3, None)], "headers": headers}]
    )
    resource = JsonFeatures(key="map_locations", club="testclub", type="points_of_interest")

    proofs = {}
    rows = list(resource.rows(proofs))

    assert proofs == {"raw_testclub__map_locations": 3}
    assert [row["geometry"] for row in rows] == [{"type": "Point", "coordinates": [-74.0, 41.0]}] * 2 + [None]
    assert all("author" not in row for row in rows), "a WordPress user id is a person's"
    assert rows[0]["title"] == '{"rendered":"Fixture 1"}', "a nested field lands as its JSON text"
    assert all(request.qs.get("_latlng") == ["acf_loc_address"] for request in requests_mock.request_history), (
        "the site's own map's query rides every page"
    )


def test_a_json_api_that_needs_a_key_is_unavailable_without_one_never_an_empty_answer(registry, monkeypatch):
    monkeypatch.delenv("FIXTURE_TEST_API_KEY", raising=False)
    resource = JsonFeatures(key="nps_places", club="testclub", type="places")

    with pytest.raises(Unavailable):
        resource.change_check(None)
    with pytest.raises(Unavailable):
        list(resource.rows({}))


def test_a_start_limit_api_steps_by_the_rows_each_page_returned_and_sends_its_key_in_a_header(
    registry, requests_mock, monkeypatch
):
    monkeypatch.setenv("FIXTURE_TEST_API_KEY", "fixture-key")

    def page(request, context):
        start = int(request.qs["start"][0])
        data = [
            {"id": f"id-{n}", "latitude": "41.0", "longitude": "-74.0", "images": [{"credit": "Fixture Person"}]}
            for n in range(start, min(start + 1, 3))
        ]
        return {"total": "3", "data": data}  # a server capping pages at 1 row, below the 2 asked for

    requests_mock.get(NPS_URL, json=page)

    proofs = {}
    rows = list(JsonFeatures(key="nps_places", club="testclub", type="places").rows(proofs))

    assert [row["id"] for row in rows] == ["id-0", "id-1", "id-2"]
    assert proofs == {"raw_testclub__nps_places": 3}
    assert all("images" not in row for row in rows), "a photographer's credit never loads"
    assert all(
        request.headers["X-Api-Key"] == "fixture-key" and "fixture-key" not in request.url
        for request in requests_mock.request_history
    )


def test_a_paged_list_that_moves_during_the_read_is_read_again_and_the_consistent_read_lands(
    registry, requests_mock, monkeypatch, capsys
):
    """Monthly run 17 (refresh-reference.yml 37232256991): nps_api_places landed one `id` on two rows that differ."""
    monkeypatch.setenv("FIXTURE_TEST_API_KEY", "fixture-key")
    pages = {"asked": 0}

    def page(request, context):
        pages["asked"] += 1
        start, first_read = int(request.qs["start"][0]), pages["asked"] <= 3
        if first_read and start == 1:
            item = {"id": "id-0", "title": "edited"}  # id-0 edited and moved up a place mid-read; id-1 never sent
        elif first_read and start == 0:
            item = {"id": "id-0", "title": "before the edit"}
        else:
            item = {"id": f"id-{start}", "title": "edited"}
        return {"total": "3", "data": [{**item, "latitude": "41", "longitude": "-74"}]}

    requests_mock.get(NPS_URL, json=page)

    proofs = {}
    rows = list(JsonFeatures(key="nps_places", club="testclub", type="places").rows(proofs))

    assert [row["id"] for row in rows] == ["id-0", "id-1", "id-2"]
    assert proofs == {"raw_testclub__nps_places": 3}
    assert "read an item twice::2 distinct of 3 items, the API counts 3; reading the list again, once" in capsys.readouterr().out


def test_a_paged_list_whose_copies_differ_on_two_reads_is_refused_with_the_fields_that_differ(
    registry, requests_mock, monkeypatch
):
    monkeypatch.setenv("FIXTURE_TEST_API_KEY", "fixture-key")

    def page(request, context):
        start = int(request.qs["start"][0])
        item = {"id": "id-0" if start < 2 else "id-2", "title": f"t{start}", "credit": "Fixture Person", "latitude": "41"}
        return {"total": "3", "data": [{**item, "longitude": "-74"}]}

    requests_mock.get(NPS_URL, json=page)

    with pytest.raises(RuntimeError, match=r"nps_places: 1 id value\(s\) on items that differ \(first: id-0, in title\)"):
        list(JsonFeatures(key="nps_places", club="testclub", type="places").rows({}))
    assert len(requests_mock.request_history) == 6, "read twice, three pages each"


def test_a_next_url_api_follows_the_url_each_page_names_until_none(registry, requests_mock):
    second = f"{VENUES_URL}/?page=2"
    requests_mock.get(
        VENUES_URL,
        json={"total": 2, "next_rest_url": second, "venues": [{"id": 1, "geo_lat": 36.5, "geo_lng": -87.3, "phone": "555-0100"}]},
    )
    requests_mock.get(second, json={"total": 2, "venues": [{"id": 2}]})

    rows = list(JsonFeatures(key="venues", club="testclub", type="places").rows({}))

    assert [row["id"] for row in rows] == ["1", "2"]
    assert rows[0]["geometry"] == {"type": "Point", "coordinates": [-87.3, 36.5]}
    assert "phone" not in rows[0], "PERSON_SHAPED"


def test_the_json_change_check_hashes_every_id_and_modified_date_and_moves_when_one_does(registry, requests_mock):
    headers = {"X-WP-Total": "2", "X-WP-TotalPages": "1"}
    requests_mock.get(
        WP_URL,
        [{"json": [location(1), location(2)], "headers": headers}] * 2
        + [{"json": [location(1), {**location(2), "modified_gmt": "2026-10-01T00:00:00"}], "headers": headers}],
    )
    resource = JsonFeatures(key="map_locations", club="testclub", type="points_of_interest")

    first, marker = resource.change_check(None)
    again, _ = resource.change_check(marker)
    moved, _ = resource.change_check(marker)

    assert (first, again, moved) == (Freshness.STALE, Freshness.FRESH, Freshness.STALE)
    assert requests_mock.request_history[0].qs["_fields"] == ["id,modified_gmt"]


def test_a_json_features_row_without_its_coordinate_fields_is_refused_at_import(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"sources": [{"key": "bad", "url": WP_URL, "paging": "wordpress"}]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    try:
        with pytest.raises(KeyError, match="lat_field"):
            json_features("bad")
    finally:
        _kinds._registry.cache_clear()


def test_the_modules_keep_the_polite_gap_decision_53_set():
    assert _gis_files.POLITE_SECONDS == _ogc.POLITE_SECONDS == _notices.DEFAULT_HOST_GAP_SECONDS == 2.0
