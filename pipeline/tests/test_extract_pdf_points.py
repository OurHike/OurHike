"""extract/_pdf_points.py, decision 54's wave 4 (section S): the points clubs print in PDFs, against mocked servers.

A parser is a function of pypdf's page texts, so most cases hand it strings shaped exactly like pypdf's plain
extraction of the live document (read 2026-10-04, each sources.json row's `notes`), with every name and number
invented, and need no pypdf: the pipeline suite installs none (requirements.in's note). The read itself is run
with fetch_club_pdfs.extract_page_texts stubbed, and once for real where pypdf is installed.

The cases are the ones a document was measured to get wrong or a hiker's safety turns on: a description that
wraps onto the lines before its numbers (ATA's Casa Blanca Canyon), a latitude printed with a space inside it,
a land manager the parser does not know, a row that wraps onto the next line or has no fix or no mile (BMTA's),
a page whose header is gone, an answer that is not a PDF, and a change check that is per file and never FRESH on
a file that sends no validator.
"""

import json

import pytest

import fetch_club_pdfs
from extract import _kinds, _notices
from extract._pdf_points import PdfLayoutChanged, PdfPoints, parse_ata_water_cache_boxes, parse_bmta_access_points, pdf_points
from lib import http_retry
from lib.freshness_state import Freshness

CACHES_URL = "https://media.example.org/uploads/water-cache-box-locations.pdf"
ACCESS_URL = "https://club.example.org/uploads/Access-PointsTrailheads.pdf"

ATA_TEXT = (
    "Arizona Trail Bear Box/Water Cache Locations\n"
    "Location Land Manager Closest Existing FarOut (NOBO) Actual Bear Box Location: (Lat/Long)\n"
    "Description Waypoint mile # Latitude Longitude Location Notes\n"
    "Fixture Pass Trailhead Coronado NF 02-138/03-000 34 31.5128627  -110.5582413 Located at Fixture Pass \n"
    "Fixture Canyon Trailhead Fixture Restoration \n"
    "Network\n"
    "04-002 51.9 31.60096 -110.72433 Located 20’ east of the fixture kiosk through the trail \n"
    "gate\n"
    "Fixture Road Trailhead Pima County 07-067b 106.5 31.9626765147121 -110.6730347405770 Located on trail \n"
    "Fixture Junction Kaibab NF 41-107 771.7 36. 851650 -112.1511540000000 Located at the junction\n"
)


def ata(text: str = ATA_TEXT) -> list[dict]:
    return parse_ata_water_cache_boxes([text])


@pytest.fixture
def known_fixture_manager(monkeypatch):
    """The fixture's invented 'Fixture Restoration Network' stands where the live table names a real one."""
    from extract import _pdf_points

    monkeypatch.setattr(_pdf_points, "ATA_LAND_MANAGERS", (*_pdf_points.ATA_LAND_MANAGERS, "Fixture Restoration Network"))


def test_each_cache_box_lands_its_manager_waypoint_mile_and_fix_and_none_of_its_notes(known_fixture_manager):
    rows = ata()

    assert [(row["name"], row["land_manager"], row["farout_waypoint"], row["mile_nobo"]) for row in rows] == [
        ("Fixture Pass Trailhead", "Coronado NF", "02-138/03-000", 34.0),
        ("Fixture Canyon Trailhead", "Fixture Restoration Network", "04-002", 51.9),
        ("Fixture Road Trailhead", "Pima County", "07-067b", 106.5),
        ("Fixture Junction", "Kaibab NF", "41-107", 771.7),
    ]
    assert rows[0]["geometry"] == {"type": "Point", "coordinates": [-110.5582413, 31.5128627]}
    assert all("notes" not in name for row in rows for name in row)


def test_a_latitude_printed_with_a_space_inside_it_is_read_as_one_number(known_fixture_manager):
    assert ata()[3]["geometry"]["coordinates"] == [-112.151154, 36.85165]


def test_a_cache_box_whose_land_manager_the_parser_does_not_know_refuses_the_document():
    with pytest.raises(PdfLayoutChanged, match="land manager"):
        ata()  # 'Fixture Restoration Network' is not one the live table named


def test_a_cache_table_without_its_title_and_header_is_refused_rather_than_read():
    with pytest.raises(PdfLayoutChanged, match="does not open"):
        ata(ATA_TEXT.replace("Arizona Trail Bear Box/Water Cache Locations", "Arizona Trail Water Report"))


BMTA_HEADER = (
    "At Mile: Location Trail Head Name\nBMT Section # \nLinked to REI: \nHiking Project\nRoad Name Link 2 Latitude Longitude\n"
)
BMTA_PAGE = (
    "Page 1 of 1\n" + BMTA_HEADER + "1.7 Fixture Gap FS 42 Fixture Gap 1a-1b FS 42 Fixture Road N34° 38.116 W84° 10.452\n"
    "28.8 Fixture Gap (GA Hwy 60, \n"
    "northern crossing) Fixture Gap 4b-5a GA Hwy 60 5a-5c N34° 48.450 W84° 11.247\n"
    "46 Fixture Creek Road Fixture Creek 6d-7a Fixture Creek Rd 7a-7d\n"
    "48.6 Fixture Hwy Fixture Hwy 7a-7b Fixture Hwy N34° 48.719 W84°22.135\n"
    "End of Fixture Dam Rd AT Fixture Trail 19e-20a Fixture Dam Rd N35° 27.626 W83° 48.668\n"
    "Access Points / Trailheads\n"
    "GEORGIA\n"
    "5/24/2020\n"
)


def test_a_wrapped_access_point_is_one_row_and_its_columns_stay_fused_never_split_by_guesswork():
    rows = parse_bmta_access_points([BMTA_PAGE])

    assert [(row["mile"], row["description"]) for row in rows] == [
        (1.7, "Fixture Gap FS 42 Fixture Gap 1a-1b FS 42 Fixture Road"),
        (28.8, "Fixture Gap (GA Hwy 60, northern crossing) Fixture Gap 4b-5a GA Hwy 60 5a-5c"),
        (46.0, "Fixture Creek Road Fixture Creek 6d-7a Fixture Creek Rd 7a-7d"),
        (48.6, "Fixture Hwy Fixture Hwy 7a-7b Fixture Hwy"),
        (None, "End of Fixture Dam Rd AT Fixture Trail 19e-20a Fixture Dam Rd"),
    ]
    lon, lat = rows[0]["geometry"]["coordinates"]
    assert (round(lat, 5), round(lon, 5)) == (34.63527, -84.1742)


def test_an_access_point_with_no_fix_lands_with_no_geometry_and_the_next_row_still_starts_at_its_mile():
    rows = parse_bmta_access_points([BMTA_PAGE])

    assert rows[2]["geometry"] is None
    assert rows[3]["geometry"]["coordinates"][0] == pytest.approx(-84.368917, abs=1e-5)  # "W84°22.135", no space


def test_an_access_point_page_without_its_header_refuses_the_document():
    with pytest.raises(PdfLayoutChanged, match="page 2 lacks"):
        parse_bmta_access_points([BMTA_PAGE, BMTA_PAGE.replace("Road Name Link 2 Latitude Longitude\n", "")])


# --- the resource ----------------------------------------------------------------------------------------------------


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    sources = [
        {"key": "ata_water_cache_boxes", "url": CACHES_URL},
        {"key": "bmta_access_points", "url": ACCESS_URL, "crawl_delay": 60},
    ]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)


def resource(key: str = "bmta_access_points") -> PdfPoints:
    return PdfPoints(key=key, club="testclub", type="points_of_interest")


def test_the_change_check_is_the_files_etag_and_fresh_only_while_it_holds(registry, requests_mock):
    requests_mock.head(ACCESS_URL, headers={"ETag": '"one"', "Last-Modified": "Fri, 01 Aug 2025 17:18:40 GMT"})
    verdict, marker = resource().change_check(None)

    assert (verdict, marker) == (Freshness.STALE, {"etag": '"one"'})
    assert resource().change_check(marker)[0] is Freshness.FRESH
    requests_mock.head(ACCESS_URL, headers={"ETag": '"two"'})
    assert resource().change_check(marker)[0] is Freshness.STALE


def test_a_file_with_no_etag_is_checked_by_its_last_modified_and_length_and_with_neither_is_unknown(registry, requests_mock):
    requests_mock.head(ACCESS_URL, headers={"Last-Modified": "Fri, 01 Aug 2025 17:18:40 GMT", "Content-Length": "530133"})
    assert resource().change_check(None)[1] == {"last_modified": "Fri, 01 Aug 2025 17:18:40 GMT", "content_length": "530133"}

    requests_mock.head(ACCESS_URL, headers={"Last-Modified": "Fri, 01 Aug 2025 17:18:40 GMT"})
    assert resource().change_check({"etag": '"one"'}) == (Freshness.UNKNOWN, None)


def test_a_wall_answered_to_the_head_is_unknown_and_the_file_is_read(registry, requests_mock):
    requests_mock.head(ACCESS_URL, status_code=403)
    assert resource().change_check({"etag": '"one"'}) == (Freshness.UNKNOWN, None)


def test_the_read_lands_each_row_with_the_documents_manifest(registry, requests_mock, monkeypatch):
    requests_mock.get(ACCESS_URL, content=b"%PDF-1.7 fixture", headers={"ETag": '"one"', "Last-Modified": "Fri, 01 Aug 2025"})
    monkeypatch.setattr(fetch_club_pdfs, "extract_page_texts", lambda body: [BMTA_PAGE])
    proofs = {}

    rows = list(resource().rows(proofs))

    assert proofs == {"raw_testclub__bmta_access_points": 5}
    assert {(row["source_url"], row["document_etag"], row["document_bytes"]) for row in rows} == {(ACCESS_URL, '"one"', 16)}
    assert len({row["document_sha256"] for row in rows}) == 1
    assert requests_mock.last_request.headers["User-Agent"] == _kinds.USER_AGENT


def test_an_html_page_answered_where_the_pdf_was_is_refused_not_parsed(registry, requests_mock):
    requests_mock.get(ACCESS_URL, text="<html>Moved</html>", headers={"Content-Type": "text/html"})

    with pytest.raises(PdfLayoutChanged, match="not a PDF"):
        list(resource().rows({}))


def test_a_real_pdf_is_read_through_pypdf_where_the_extract_job_installs_it(registry, requests_mock):
    """Needs pypdf, which only requirements-extract.txt pins, so the pipeline suite's environment skips it."""
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = __import__("io").BytesIO()
    writer.write(buffer)
    requests_mock.get(ACCESS_URL, content=buffer.getvalue())

    with pytest.raises(PdfLayoutChanged, match="lacks"):  # a blank page has no header: refused, never an empty table
        list(resource().rows({}))


def test_a_pdf_key_with_no_parser_is_refused_at_import(registry):
    sources = json.loads(registry.read_text())["sources"] + [{"key": "no_such_pdf", "url": ACCESS_URL}]
    registry.write_text(json.dumps({"sources": sources}))
    _kinds._registry.cache_clear()
    with pytest.raises(KeyError, match="no parser"):
        pdf_points("no_such_pdf")
