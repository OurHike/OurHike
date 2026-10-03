"""extract/_json_apis.py, the JSON API notice readers (ELT.md decision 53, phase B), against mocked servers.

Each reader is run through the hourly lane into a `file://` raw store under
tmp_path, as tests/test_extract_run.py runs the ArcGIS ones, or asked for its
rows directly where only the read is in question. requests_mock answers as
each upstream did when the decision 53 inventory read it on 2026-10-03; the
bodies are invented and shaped like those answers. Nothing reaches the
network: conftest.py's socket guard stays on.

The cases are the ones the zero, the key and the person fields turn on: a
park list with no alerts loads an empty table only beside the API's own
`total` of 0; a missing NPS_API_KEY withdraws the table rather than reading
as no alerts; a server that serves fewer alerts than asked still yields every
one; a lead-contamination advisory survives to the warehouse whole; and the
columns that name people never reach a row.
"""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from extract import _json_apis, _kinds
from extract._contract import Unavailable
from extract._json_apis import (
    SHEET_PERSON_COLUMNS,
    DcnrParkAdvisories,
    MediawikiAnnouncements,
    MyMapsPlacemarks,
    NpsAlerts,
    NpsRoadEvents,
    SheetCsvSegments,
    UsgsElevatedVolcanoes,
    advisory_key,
    nps_alerts,
    parse_segment_sheet,
)
from lib import http_retry
from lib.freshness_state import Freshness
from tests.test_extract_run import lane, warehouse

NPS = "https://nps.example.gov/api/v1/alerts"
ROADS = "https://nps.example.gov/api/v1/roadevents"
DCNR = "https://dcnr.example.gov/ParkAddresses/api/ParkAdvisory/get"
VOLCANOES = "https://volcanoes.example.gov/hans-public/api/volcano/getElevatedVolcanoes"
WIKI = "https://club.example.org/clubwiki/api.php"
SHEET = "https://sheets.example.com/spreadsheets/d/abc/export?format=csv&gid=1"
KML_URL = "https://maps.example.com/maps/d/kml?mid=abc&forcekml=1"
LEAD = (
    "<p>The unnamed stream between mile-marker 31 and 32 has been contaminated by lead and other heavy metals.&nbsp; "
    "Please do not use this as a drinking water source.</p>\r\n<p></p>"
)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding one entry per reader, in place of the real one."""
    path = tmp_path / "sources.json"
    sources = [
        {"key": "nps_alerts", "url": NPS, "park_codes": {"semo": ["semo"], "grsm": ["bmta", "nc-mst"]}},
        {"key": "nps_road_events", "url": ROADS},
        {"key": "pa_dcnr_park_advisories", "url": DCNR, "park_ids": {"6219": ["laurel"], "8116": ["pasda"]}},
        {"key": "usgs_elevated_volcanoes", "url": VOLCANOES},
        {"key": "tehcc_wiki_announcements", "url": WIKI, "template": "Template:Announcement"},
        {"key": "foot_trail_condition_report", "url": SHEET},
        {"key": "fmst_helene_status", "url": KML_URL},
    ]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_gap(monkeypatch):
    """No host is asked anything, so the readers' 2 s courtesy gap is 0 here."""
    monkeypatch.setattr(_json_apis, "POLITE_GAP_SECONDS", 0)
    monkeypatch.setattr(_json_apis, "_LAST_REQUEST_END", {})


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv(_json_apis.NPS_API_KEY_ENV, "test-key-not-real")


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


def query(request) -> dict:
    """The request's query, parsed with its case kept (requests_mock's own `qs` lowercases values)."""
    return {name: values[0] for name, values in parse_qs(urlsplit(request.url).query).items()}


def alert(number, park="semo", category="Park Closure"):
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "url": "",
        "title": f"Fixture alert {number}",
        "parkCode": park,
        "description": f"Fixture description {number}.",
        "category": category,
        "relatedRoadEvents": [],
        "lastIndexedDate": "2026-10-02 00:00:00.0",
    }


class FakeNps:
    """NPS's alerts API: `total` as a string, pages of at most `cap` whatever `limit` asks, `start` an offset."""

    def __init__(self, requests_mock, alerts, cap=500):
        self.alerts, self.cap, self.asked = alerts, cap, []
        requests_mock.get(NPS, json=self.answer)

    def answer(self, request, context):
        params = query(request)
        self.asked.append((params, request.headers.get("X-Api-Key")))
        start, limit = int(params["start"]), int(params["limit"])
        page = self.alerts[start : start + min(limit, self.cap)]
        return {"total": str(len(self.alerts)), "limit": str(limit), "start": str(start), "data": page}


def nps():
    return NpsAlerts(key="nps_alerts", club="nps", type="warnings")


# --- NPS alerts -------------------------------------------------------------------


def test_nps_alerts_land_every_alert_when_the_server_serves_fewer_than_asked(registry, key, requests_mock):
    server = FakeNps(requests_mock, [alert(n) for n in range(5)], cap=2)

    proofs = {}
    rows = list(nps().rows(proofs))

    assert [row["id"] for row in rows] == [alert(n)["id"] for n in range(5)]
    assert [params["start"] for params, _ in server.asked] == ["0", "2", "4"], "steps by rows returned, not by limit"
    assert proofs == {"raw_nps__nps_alerts": 5}
    assert {params["parkCode"] for params, _ in server.asked} == {"grsm,semo"}, "every listed code, in one request"


def test_the_nps_key_travels_in_a_header_and_never_in_a_url(registry, key, requests_mock):
    server = FakeNps(requests_mock, [alert(1)])

    list(nps().rows({}))

    assert [header for _, header in server.asked] == ["test-key-not-real"]
    assert all("test-key-not-real" not in request.url for request in requests_mock.request_history)


def test_a_park_list_with_no_alerts_loads_an_empty_table_beside_the_apis_own_total_of_zero(registry, key, store, requests_mock):
    FakeNps(requests_mock, [alert(1), alert(2)])
    lane(store, nps())

    FakeNps(requests_mock, [])
    report = lane(store, nps())

    assert report.outcome == "loaded"
    assert report.rows["raw_nps__nps_alerts"] == 0
    assert report.proofs["raw_nps__nps_alerts"] == 0
    con, counts = warehouse(store)
    assert counts["raw_nps__nps_alerts"] == 0, "every alert lifted leaves by its absence"
    columns = {row[0] for row in con.execute("describe raw.raw_nps__nps_alerts").fetchall()}
    assert {"id", "title", "category", "parkcode", "lastindexeddate"} <= columns, "hinted, so a zero still has its columns"


def test_without_an_nps_key_the_alerts_are_unavailable_and_their_table_is_withdrawn(
    registry, key, store, requests_mock, monkeypatch
):
    FakeNps(requests_mock, [alert(1), alert(2)])
    lane(store, nps())
    asked_before = requests_mock.call_count

    monkeypatch.delenv(_json_apis.NPS_API_KEY_ENV)
    report = lane(store, nps())

    assert "raw_nps__nps_alerts" in report.unavailable
    assert requests_mock.call_count == asked_before, "nothing is asked of NPS without a key"
    _, counts = warehouse(store)
    assert "raw_nps__nps_alerts" not in counts, "a missing secret reads as unknown, never as no alerts"


def test_an_empty_nps_api_key_is_as_missing_as_an_unset_one(monkeypatch):
    monkeypatch.setenv(_json_apis.NPS_API_KEY_ENV, "  ")
    with pytest.raises(Unavailable, match="NPS_API_KEY"):
        _json_apis.nps_api_key()


def test_a_total_that_moves_between_pages_refuses_the_read(registry, key, requests_mock):
    totals = iter(["3", "4"])
    requests_mock.get(NPS, json=lambda request, context: {"total": next(totals), "data": [alert(int(query(request)["start"]))]})

    with pytest.raises(RuntimeError, match="counted 3 alerts and then 4"):
        list(nps().rows({}))


def test_a_page_served_twice_refuses_the_read_rather_than_doubling_an_alert(registry, key, requests_mock):
    requests_mock.get(NPS, json={"total": "2", "data": [alert(1)]})

    with pytest.raises(RuntimeError, match="missing or repeated"):
        list(nps().rows({}))


def test_an_nps_answer_without_a_total_refuses_rather_than_proving_a_zero(registry, key, requests_mock):
    requests_mock.get(NPS, json={"data": []})

    with pytest.raises(ValueError, match="no `total`"):
        list(nps().rows({}))


def test_an_nps_entry_that_lists_no_park_codes_is_refused_when_its_file_is_read(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [{"key": "nps_alerts", "url": NPS}]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    try:
        with pytest.raises(KeyError, match="park_codes"):
            nps_alerts("nps_alerts")
    finally:
        _kinds._registry.cache_clear()


# --- NPS road events ----------------------------------------------------------------


def road_feed(features):
    return {
        "road_event_feed_info": {
            "publisher": "National Park Service",
            "update_date": "2026-10-01T00:00:00Z",
            "contact_name": "Fixture Publisher",
            "contact_email": "publisher@example.invalid",
            "data_sources": [
                {
                    "data_source_id": "s1",
                    "organization_name": "Fixture National Park",
                    "contact_name": "Fixture Superintendent",
                    "contact_email": "superintendent@example.invalid",
                }
            ],
        },
        "type": "FeatureCollection",
        "features": features,
    }


def road_event(number):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-119.70, 37.65], [-119.71, 37.66]]},
        "properties": {
            "core_details": {"name": f"Fixture event {number}", "data_source_id": "s1", "event_type": "incident"},
            "vehicle_impact": "all-lanes-closed",
            "Id": f"00000000-0000-4000-a000-{number:012d}",
            "_id": number,
        },
    }


def test_road_events_land_with_their_parks_name_and_never_the_feeds_contacts(registry, key, requests_mock):
    requests_mock.get(ROADS, json=road_feed([road_event(1), road_event(2)]))

    proofs = {}
    rows = list(NpsRoadEvents(key="nps_road_events", club="nps", type="warnings").rows(proofs))

    assert proofs == {"raw_nps__nps_road_events": 2}
    assert {row["data_source_organization"] for row in rows} == {"Fixture National Park"}
    text = json.dumps(rows)
    for contact in ("Fixture Publisher", "Fixture Superintendent", "publisher@example.invalid", "superintendent@example.invalid"):
        assert contact not in text, f"{contact} is a contact field and never loads"


def test_a_road_feed_with_no_events_is_a_proven_zero_and_one_that_is_not_a_feature_collection_refuses(
    registry, key, requests_mock
):
    resource = NpsRoadEvents(key="nps_road_events", club="nps", type="warnings")
    requests_mock.get(ROADS, json=road_feed([]))
    proofs = {}
    assert list(resource.rows(proofs)) == [] and proofs == {"raw_nps__nps_road_events": 0}

    requests_mock.get(ROADS, json={"error": {"code": "API_KEY_INVALID"}})
    with pytest.raises(ValueError, match="not a FeatureCollection"):
        list(resource.rows({}))


# --- PA DCNR ParkAdvisory -------------------------------------------------------------


def dcnr():
    return DcnrParkAdvisories(key="pa_dcnr_park_advisories", club="pasda", type="warnings")


def advisories(requests_mock, by_park):
    requests_mock.get(DCNR, json=lambda request, context: by_park[query(request)["id"]])


def test_a_lead_contamination_advisory_round_trips_into_the_warehouse_with_its_text_whole(registry, store, requests_mock):
    statewide = {"IsAlert": False, "Message": "<p><strong>Fixture Restrictions:</strong> statewide.</p>"}
    advisories(requests_mock, {"6219": [statewide, {"IsAlert": True, "Message": LEAD}], "8116": [statewide]})

    report = lane(store, dcnr())

    assert report.rows["raw_pasda__pa_dcnr_park_advisories"] == 3
    con, _ = warehouse(store)
    alerts = con.execute(
        "select park_id, isalert, message, advisory_key from raw.raw_pasda__pa_dcnr_park_advisories where isalert"
    ).fetchall()
    assert alerts == [(6219, True, LEAD, advisory_key(6219, LEAD, 0))], "the water advisory lands whole, its park beside it"
    assert "contaminated by lead" in alerts[0][2] and "drinking water source" in alerts[0][2]


def test_two_identical_advisories_in_one_park_get_two_keys_and_the_same_two_next_run(registry, requests_mock):
    same = {"IsAlert": False, "Message": "<p>Fixture firewood quarantine.</p>"}
    advisories(requests_mock, {"6219": [same, same], "8116": [same]})

    first = [row["advisory_key"] for row in dcnr().rows({})]
    second = [row["advisory_key"] for row in dcnr().rows({})]

    assert len(set(first)) == 3, "two in Laurel Ridge and one in Tioga, the same text in each"
    assert first == second, "a key is a function of park, text and order, so an unchanged answer keeps its keys"


def test_every_park_answering_an_empty_list_is_a_proven_zero(registry, requests_mock):
    advisories(requests_mock, {"6219": [], "8116": []})

    proofs = {}
    assert list(dcnr().rows(proofs)) == []
    assert proofs == {"raw_pasda__pa_dcnr_park_advisories": 0}


def test_a_park_answering_anything_but_a_list_refuses_the_read(registry, requests_mock):
    advisories(requests_mock, {"6219": {"Message": "Service unavailable"}, "8116": []})

    with pytest.raises(ValueError, match="not a list of advisories"):
        list(dcnr().rows({}))


# --- USGS elevated volcanoes -----------------------------------------------------------


def volcano(vnum, notice="DOI-USGS-FIX-2026-10-02T00:00:00+00:00"):
    return {
        "vnum": vnum,
        "volcano_name": f"Fixture {vnum}",
        "notice_identifier": notice,
        "color_code": "YELLOW",
        "sent_unixtime": 1,
    }


def test_volcanoes_sharing_one_notice_land_one_row_each(registry, requests_mock):
    requests_mock.get(VOLCANOES, json=[volcano("900001"), volcano("900002")])

    proofs = {}
    rows = list(UsgsElevatedVolcanoes(key="usgs_elevated_volcanoes", club="usgs", type="warnings").rows(proofs))

    assert [row["vnum"] for row in rows] == ["900001", "900002"]
    assert proofs == {"raw_usgs__usgs_elevated_volcanoes": 2}


def test_a_volcano_listed_twice_refuses_the_read_because_vnum_keys_the_table(registry, requests_mock):
    requests_mock.get(VOLCANOES, json=[volcano("900001"), volcano("900001")])

    with pytest.raises(RuntimeError, match="listed twice"):
        list(UsgsElevatedVolcanoes(key="usgs_elevated_volcanoes", club="usgs", type="warnings").rows({}))


# --- MediaWiki announcements -------------------------------------------------------------


def wiki_page(pageid, touched="2026-09-22T01:06:28Z", revid=101):
    return {
        "pageid": pageid,
        "ns": 0,
        "title": f"Fixture {pageid}",
        "touched": touched,
        "lastrevid": revid,
        "fullurl": f"{WIKI}?curid={pageid}",
    }


class FakeWiki:
    """A MediaWiki API: the template's page, then the embeddedin listing in two continuation batches."""

    def __init__(self, requests_mock, pages, template_exists=True):
        self.pages, self.template_exists, self.asked = pages, template_exists, []
        requests_mock.get(WIKI, json=self.answer)

    def answer(self, request, context):
        params = query(request)
        self.asked.append(params)
        if "titles" in params:
            page = {"ns": 10, "title": params["titles"]}
            return {
                "batchcomplete": True,
                "query": {"pages": [page | ({"pageid": 9000} if self.template_exists else {"missing": True})]},
            }
        revisions = "revisions" in params.get("prop", "")

        def shaped(page):
            if not revisions:
                return page
            slots = {"main": {"content": f"{{{{Announcement|Fixture {page['pageid']}}}}}"}}
            return {**page, "revisions": [{"revid": page["lastrevid"], "timestamp": page["touched"], "slots": slots}]}

        half = len(self.pages) // 2
        if "geicontinue" not in params:
            return {
                "continue": {"geicontinue": "next", "continue": "gcontinue||"},
                "query": {"pages": [shaped(p) for p in self.pages[:half]]},
            }
        return {"batchcomplete": True, "query": {"pages": [shaped(p) for p in self.pages[half:]]}}


def wiki():
    return MediawikiAnnouncements(key="tehcc_wiki_announcements", club="tehcc", type="warnings")


def test_wiki_announcements_land_one_row_per_page_across_batches_without_the_editors_name(registry, requests_mock):
    server = FakeWiki(requests_mock, [wiki_page(1), wiki_page(2), wiki_page(3)])

    proofs = {}
    rows = list(wiki().rows(proofs))

    assert [row["pageid"] for row in rows] == [1, 2, 3]
    assert rows[0]["content"] == "{{Announcement|Fixture 1}}"
    assert proofs == {"raw_tehcc__tehcc_wiki_announcements": 3}
    asked = [params.get("rvprop") for params in server.asked if params.get("rvprop")]
    assert asked and all(set(rvprop.split("|")) == {"ids", "timestamp", "content"} for rvprop in asked), (
        "the revision's user and comment are never asked for"
    )


def test_the_wiki_check_moves_when_a_template_the_page_carries_is_edited(registry, requests_mock):
    FakeWiki(requests_mock, [wiki_page(1), wiki_page(2)])
    first, marker = wiki().change_check(None)
    assert first is Freshness.STALE

    FakeWiki(requests_mock, [wiki_page(1), wiki_page(2)])
    assert wiki().change_check(marker)[0] is Freshness.FRESH

    FakeWiki(requests_mock, [wiki_page(1), wiki_page(2, touched="2026-10-03T00:00:00Z")])
    assert wiki().change_check(marker)[0] is Freshness.STALE, "touched moved with no new revision of the page"


def test_a_missing_announcement_template_refuses_rather_than_lifting_every_announcement(registry, requests_mock):
    FakeWiki(requests_mock, [], template_exists=False)

    with pytest.raises(RuntimeError, match="missing from the wiki"):
        list(wiki().rows({}))


def test_a_wiki_change_check_that_cannot_ask_is_unknown(registry, requests_mock, monkeypatch):
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)
    requests_mock.get(WIKI, exc=requests.ConnectionError)

    assert wiki().change_check({"count": "1"}) == (Freshness.UNKNOWN, None)


# --- the condition-report sheet ------------------------------------------------------------

SHEET_TEXT = "\n".join(
    [
        ",,,,10/1/2026,,,,,,",
        "Fixture Trail CONDITION REPORT,,,,,,,,,,",
        'Sect,Ranger District,Begin,End,Description,Miles,Adopted by,Last Condition Report Submitted,"Source of Last  '
        'Condition Report \n",Comments,"Shelter\nDistance"',
        "1,Fixture District,0.0,2.4,Fixture TH to Vista,2.4,Person Alpha,10/25,Person Beta,,",
        "1,Fixture District,2.4,5.8,Vista to FR 1,3.4,Person Gamma,9/25,Person Delta,Down tree removed,6.2",
        ",,,,,,,,,,223.0",
        "Fixture Loop CONDITION REPORT,,,,,,,,,,",
        "Sect,Ranger District,Begin,End,Description,Miles,Adopted by,Last Condition Report Submitted,Source of Last "
        "Condition Report,Comments,",
        "FL,Fixture District,0.0,1.5,Loop start to campsite,1.5,Person Epsilon,11/23,Person Zeta,,",
        ",Color Codes:,,Green=trail is clear,,,,,,,",
    ]
)


def test_a_condition_sheet_lands_every_segment_and_never_a_column_that_names_people(registry, requests_mock):
    requests_mock.get(SHEET, text=SHEET_TEXT, headers={"Content-Type": "text/csv; charset=utf-8"})

    proofs = {}
    rows = list(SheetCsvSegments(key="foot_trail_condition_report", club="ouachita", type="warnings").rows(proofs))

    assert proofs == {"raw_ouachita__foot_trail_condition_report": 3}
    assert [(row["table_title"], row["sect"], row["begin_mile"], row["end_mile"]) for row in rows] == [
        ("Fixture Trail CONDITION REPORT", "1", "0.0", "2.4"),
        ("Fixture Trail CONDITION REPORT", "1", "2.4", "5.8"),
        ("Fixture Loop CONDITION REPORT", "FL", "0.0", "1.5"),
    ]
    assert rows[1]["comments"] == "Down tree removed" and rows[1]["shelter_distance"] == "6.2"
    assert {row["report_date"] for row in rows} == {"10/1/2026"}
    assert "Person" not in json.dumps(rows), "Adopted by and Source of Last Condition Report never load"
    assert not SHEET_PERSON_COLUMNS & set(_json_apis.SHEET_COLUMNS), "no person column is on the allow list"


def test_a_column_the_sheet_adds_is_not_loaded_until_somebody_reads_it(registry):
    text = "Fixture CONDITION REPORT,,,,\nSect,Begin,End,Reported by,Comments\n1,0.0,1.0,Person Eta,Clear\n"

    _, rows = parse_segment_sheet(text)

    assert rows == [
        {
            "table_title": "Fixture CONDITION REPORT",
            "sect": "1",
            "begin_mile": "0.0",
            "end_mile": "1.0",
            "comments": "Clear",
            "row_number": 3,
            "report_date": None,
        }
    ], "an unknown column is dropped, and a missing report date stays missing"


def test_a_sheet_that_lost_its_segment_header_or_its_segments_refuses(registry):
    with pytest.raises(ValueError, match="without"):
        parse_segment_sheet("Title,,\nSect,Ranger District,Description\n1,Fixture,Somewhere\n")
    with pytest.raises(ValueError, match="no segment rows"):
        parse_segment_sheet("Title,,\nSect,Begin,End\n,,\n")


# --- the My Maps KML -------------------------------------------------------------------

KML_TEXT = (
    '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Fixture</name>'
    "<Folder><name>Fixture Route</name>"
    "<Placemark><name>Fixture Gap to Fixture Ford</name><description><![CDATA[Name   Fixture Gap    <br>   Trail Status   "
    "CLOSED]]></description><styleUrl>#line-FF0000-4000</styleUrl><LineString><coordinates>-81.9,35.8,0 -81.8,35.9,0"
    "</coordinates></LineString></Placemark>"
    "<Placemark><name>Fixture Spring</name><Point><coordinates>-81.7,35.7,0</coordinates></Point></Placemark>"
    "</Folder></Document></kml>"
)


def test_a_my_maps_kml_lands_each_placemark_with_its_status_text_style_and_geometry(registry, requests_mock):
    requests_mock.get(KML_URL, text=KML_TEXT, headers={"Content-Type": "text/xml; charset=utf-8"})

    proofs = {}
    rows = list(MyMapsPlacemarks(key="fmst_helene_status", club="fmst", type="closures").rows(proofs))

    assert proofs == {"raw_fmst__fmst_helene_status": 2}
    closed, spring = rows
    assert (closed["folder"], closed["name"], closed["style_url"]) == (
        "Fixture Route",
        "Fixture Gap to Fixture Ford",
        "#line-FF0000-4000",
    )
    assert closed["description"].endswith("Trail Status   CLOSED"), "the status lands as served, for dbt to read"
    assert closed["geometry"] == {"type": "LineString", "coordinates": [[-81.9, 35.8], [-81.8, 35.9]]}
    assert spring["geometry"] == {"type": "Point", "coordinates": [-81.7, 35.7]}


def test_a_status_map_with_no_placemarks_is_a_broken_read_not_every_closure_lifted(registry, requests_mock):
    empty = '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>x</name></Document></kml>'
    requests_mock.get(KML_URL, text=empty, headers={"Content-Type": "text/xml"})

    with pytest.raises(RuntimeError, match="holds no placemark"):
        list(MyMapsPlacemarks(key="fmst_helene_status", club="fmst", type="closures").rows({}))
