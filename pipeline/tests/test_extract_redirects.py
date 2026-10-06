"""Every extract reader refuses an answer served from another host than the one its row names (review finding SEC-5).

Round 1's EXD-10 fix (extract/_notices.py's redirect_refused) reached the GIS-file, JSON-API and club-PDF readers
only; the ArcGIS client, which reads 381 of the registry's 693 rows, and about ten other readers still followed a
redirect to any host and loaded what it answered, a host whose robots.txt and terms nobody read for the row. The
refusal now lives in extract/_kinds.py's session(), which every reader sends through, so each kind below is asked
through a server that answers every request with a 302 to `elsewhere.example.net`, and each must refuse rather
than read that host's answer. A redirect within the site (`www.`) and one to a host the row names in
`redirect_hosts` are still followed. Every server is mocked: conftest.py's socket guard stays on.
"""

from __future__ import annotations

import json
import re

import pytest
import requests_mock as requests_mocking

from extract import _content, _json_apis, _kinds, _notices
from extract._gis_files import GisFile, GisFileUnreadable
from extract._ogc import JsonFeatures, OgcFeatures
from extract._pdf_points import PDF_PARSERS, PdfPoints
from lib.freshness_state import Freshness

ELSEWHERE = "https://elsewhere.example.net/moved"
SITE = "https://club.example.org"
LAYER = "https://services.example.org/arcgis/rest/services/Trails/FeatureServer/0"
PDF_KEY = sorted(PDF_PARSERS)[0]

ROWS = [
    {"key": "club_layer", "url": LAYER},
    {"key": "city_fountains", "domain": "data.example.gov", "dataset_id": "abcd-1234", "kind": "socrata_geojson_layer"},
    {"key": "club_alerts", "url": f"{SITE}/category/trail-alerts/", "kind": "published_notices"},
    {"key": "club_guide_pages", "url": f"{SITE}/hike-new-mexico/"},
    {"key": "nynjtc_long_path_guide", "url": f"{SITE}/long-path-guide/", "kind": "guide_pages"},
    {"key": "hikes", "url": f"{SITE}/hikefinder/", "kind": "published_hikes"},
    {"key": "usgs_3dhp", "url": LAYER, "kind": "watched_only", "freshness": {"url": LAYER + "/query"}},
    {"key": "a_podcast", "url": f"{SITE}/feed.xml", "kind": "podcast_feed"},
    {"key": "atc_trail_updates", "url": f"{SITE}/trail-updates/"},
    {"key": "nps_alerts", "url": "https://nps.example.gov/api/v1/alerts", "park_codes": {"semo": ["semo"]}},
    {"key": "nps_audio", "url": "https://nps.example.gov/api/v1/multimedia/audio"},
    {"key": "nps_road_events", "url": "https://nps.example.gov/api/v1/roadevents"},
    {"key": "pa_dcnr_park_advisories", "url": "https://dcnr.example.gov/api/ParkAdvisory/get", "park_ids": {"6219": []}},
    {"key": "usgs_elevated_volcanoes", "url": "https://volcanoes.example.gov/api/volcano/getElevatedVolcanoes"},
    {"key": "club_wiki", "url": f"{SITE}/clubwiki/api.php", "template": "Template:Announcement"},
    {"key": "club_sheet", "url": "https://sheets.example.com/spreadsheets/d/abc/export?format=csv&gid=1"},
    {"key": "club_my_map", "url": "https://maps.example.com/maps/d/kml?mid=abc&forcekml=1"},
    {"key": PDF_KEY, "url": f"{SITE}/points.pdf"},
    {"key": "club_points", "url": f"{SITE}/points.geojson", "file_format": "geojson"},
    {"key": "club_places", "url": f"{SITE}/api/places", "paging": "single", "lat_field": "lat", "lon_field": "lon"},
    {"key": "club_collection", "url": f"{SITE}/ogc/collections/trails/items"},
    {"key": "gatc_water_sources", "url": f"{SITE}/water.pdf", "kind": "club_pdf"},
    {
        "key": "exported_map",
        "url": "https://maps.example.com/maps/d/kml?mid=moved&forcekml=1",
        "redirect_hosts": ["kml-content.example.net"],
    },
    {
        "key": "exported_sheet",
        "url": "https://docs.example.com/spreadsheets/d/abc/export?format=csv",
        "file_format": "geojson",
        "redirect_hosts": ["files.example.net"],
    },
]


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": ROWS}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    monkeypatch.setattr(_json_apis, "POLITE_GAP_SECONDS", 0)
    monkeypatch.setattr(_json_apis, "_LAST_REQUEST_END", {})
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(_kinds, "GUIDE_THROTTLE_SECONDS", 0)
    monkeypatch.setattr(_kinds, "HIKEFINDER_THROTTLE_SECONDS", 0)
    monkeypatch.setattr(_kinds.ATC_CRAWL_GATE, "finished", None)
    monkeypatch.setattr(_kinds.ATC_CRAWL_GATE, "sleep", lambda seconds: None)
    monkeypatch.setattr(_kinds, "_ATC_LISTINGS", {})
    monkeypatch.setenv(_json_apis.NPS_API_KEY_ENV, "test-key-not-real")
    monkeypatch.delenv("HIKEFINDER_PASSWORD", raising=False)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture
def moved(requests_mock):
    """Every host but `elsewhere.example.net` answers every request with a 302 there; it answers as if it were the source."""
    requests_mock.register_uri(
        requests_mocking.ANY,
        re.compile(r"^https?://(?!elsewhere\.example\.net)"),
        status_code=302,
        headers={"Location": ELSEWHERE},
    )
    for method in ("GET", "HEAD", "POST"):
        requests_mock.register_uri(method, re.compile(r"^https://elsewhere\.example\.net/"), json=[], headers={"ETag": '"e"'})
    return requests_mock


READERS = {
    "ArcgisLayer": lambda: _kinds.ArcgisLayer(key="club_layer", club="testclub", type="trail_lines"),
    "SocrataDataset": lambda: _kinds.SocrataDataset(key="city_fountains", club="testcity", type="points_of_interest"),
    "WordpressPosts": lambda: _kinds.WordpressPosts(key="club_alerts", club="testclub", type="closures"),
    "WordpressChildPages": lambda: _content.WordpressChildPages(
        key="club_guide_pages", club="testclub", type="suggested_hikes", post_type="pages", parent=2040
    ),
    "WordpressTerms": lambda: _kinds.WordpressTerms(key="club_alerts", club="testclub", type="closures", taxonomies=("trail",)),
    "SiteTerms": lambda: _content.SiteTerms(key="club_alerts", club="testclub", type="suggested_hikes", taxonomies=("trail",)),
    "GuidePages": lambda: _kinds.GuidePages(key="nynjtc_long_path_guide", club="nynjtc", type="suggested_hikes"),
    "PublishedHikes": lambda: _kinds.PublishedHikes(key="hikes", club="nynjtc", type="suggested_hikes"),
    "OpentrailFeed": lambda: _kinds.OpentrailFeed(key="at", club="opentrail", type="points_of_interest"),
    "HydrographyWatch": lambda: _kinds.HydrographyWatch(key="usgs_3dhp", club="usgs", type="elevation"),
    "BucketListing": lambda: _kinds.BucketListing(key="tnm_3dep_13_current", club="usgs", type="elevation"),
    "NwsAlerts": lambda: _kinds.NwsAlerts(key="alerts", club="nws", type="warnings"),
    "PodcastFeed": lambda: _kinds.PodcastFeed(key="a_podcast", club="testclub", type="podcasts"),
    "PodcastEpisodes": lambda: _content.PodcastEpisodes(key="a_podcast", club="testclub", type="podcasts"),
    "AtcTrailUpdatePages": lambda: _kinds.AtcTrailUpdatePages(key="atc_trail_updates", club="atc", type="closures"),
    "NpsAlerts": lambda: _json_apis.NpsAlerts(key="nps_alerts", club="nps", type="warnings"),
    "NpsContent": lambda: _content.NpsContent(key="nps_audio", club="nps", type="podcasts"),
    "NpsRoadEvents": lambda: _json_apis.NpsRoadEvents(key="nps_road_events", club="nps", type="warnings"),
    "DcnrParkAdvisories": lambda: _json_apis.DcnrParkAdvisories(key="pa_dcnr_park_advisories", club="pasda", type="warnings"),
    "UsgsElevatedVolcanoes": lambda: _json_apis.UsgsElevatedVolcanoes(
        key="usgs_elevated_volcanoes", club="usgs", type="warnings"
    ),
    "MediawikiAnnouncements": lambda: _json_apis.MediawikiAnnouncements(key="club_wiki", club="tehcc", type="closures"),
    "MediawikiTemplatePages": lambda: _content.MediawikiTemplatePages(key="club_wiki", club="tehcc", type="suggested_hikes"),
    "SheetCsvSegments": lambda: _json_apis.SheetCsvSegments(key="club_sheet", club="testclub", type="warnings"),
    "MyMapsPlacemarks": lambda: _json_apis.MyMapsPlacemarks(key="club_my_map", club="testclub", type="closures"),
    "PdfPoints": lambda: PdfPoints(key=PDF_KEY, club="testclub", type="points_of_interest"),
    # Round 1's readers, held to the same refusal now that it lives in the session.
    "GisFile": lambda: GisFile(key="club_points", club="testclub", type="points_of_interest"),
    "JsonFeatures": lambda: JsonFeatures(key="club_places", club="testclub", type="places"),
    "OgcFeatures": lambda: OgcFeatures(key="club_collection", club="testclub", type="trail_lines"),
    "ClubPdf": lambda: _kinds.ClubPdf(key="gatc_water_sources", club="gatc", type="points_of_interest"),
}


@pytest.mark.parametrize("kind", READERS)
def test_every_reader_refuses_an_answer_redirected_to_another_host_and_its_change_check_is_unknown(registry, moved, kind):
    resource = READERS[kind]()

    with pytest.raises(Exception, match="another host"):
        list(resource.rows({}))
    assert resource.change_check(None)[0] is Freshness.UNKNOWN, "a check answered from another host is no marker"


def test_an_arcgis_layer_redirected_to_another_host_lands_none_of_that_hosts_features(registry, requests_mock):
    """The finding's own reproduction, through the reader: the other host answers as a layer would, and is not read."""
    elsewhere = "https://unread-host.example.net/arcgis/rest/services/Trails/FeatureServer/0"
    requests_mock.get(LAYER, status_code=302, headers={"Location": elsewhere})
    requests_mock.get(LAYER + "/query", status_code=302, headers={"Location": elsewhere + "/query"})
    fields = [{"name": "OBJECTID", "type": "esriFieldTypeOID"}, {"name": "NAME", "type": "esriFieldTypeString"}]
    requests_mock.get(elsewhere, json={"fields": fields, "objectIdField": "OBJECTID"}, headers={"ETag": '"x"'})
    feature = {"type": "Feature", "id": 1, "geometry": None, "properties": {"OBJECTID": 1, "NAME": "from the other host"}}

    def query(request, context):
        if request.qs.get("returncountonly") == ["true"]:
            return {"count": 1}
        offset = int(request.qs.get("resultoffset", ["0"])[0])
        return {"type": "FeatureCollection", "features": [feature] if offset == 0 else []}

    requests_mock.get(elsewhere + "/query", json=query)
    layer = _kinds.ArcgisLayer(key="club_layer", club="testclub", type="trail_lines")

    with pytest.raises(Exception, match=r"redirects to https://unread-host\.example\.net/\S*, another host"):
        list(layer.rows({}))
    assert layer.change_check(None) == (Freshness.UNKNOWN, None)


@pytest.mark.parametrize(
    ("key", "served"),
    [("club_points", "https://www.club.example.org/points.geojson"), ("exported_sheet", "https://doc-1.files.example.net/x")],
    ids=["the same site under www", "a host the row names in redirect_hosts"],
)
def test_a_redirect_within_the_site_or_to_a_host_the_row_has_read_is_still_followed(registry, requests_mock, key, served):
    url = next(row["url"] for row in ROWS if row["key"] == key)
    requests_mock.get(url, status_code=301, headers={"Location": served})
    one = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"n": 1}, "geometry": None}]}
    requests_mock.get(served, json=one)

    assert len(list(GisFile(key=key, club="testclub", type="points_of_interest").rows({}))) == 1


def test_a_json_api_reader_passes_its_row_so_a_host_the_row_names_is_followed(registry, requests_mock):
    """foot_trail_condition_report's Google Sheets export answers from a googleusercontent.com host (its row's licence
    text, 2026-10-03), so a reader of _json_apis.py's must hand its row to the session for `redirect_hosts` to count."""
    served = "https://doc-04.kml-content.example.net/export"
    requests_mock.get("https://maps.example.com/maps/d/kml?mid=moved&forcekml=1", status_code=307, headers={"Location": served})
    kml = (
        '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>Fixture Gap</name>'
        "<Point><coordinates>-81.7,35.7,0</coordinates></Point></Placemark></Document></kml>"
    )
    requests_mock.get(served, text=kml, headers={"Content-Type": "application/vnd.google-earth.kml+xml"})

    rows = list(_json_apis.MyMapsPlacemarks(key="exported_map", club="testclub", type="closures").rows({}))

    assert [row["name"] for row in rows] == ["Fixture Gap"]


def test_a_gis_file_still_refuses_a_redirect_with_its_own_error(registry, moved):
    """GisFile's change check and read deal in GisFileUnreadable; the session's refusal arrives as one."""
    with pytest.raises(GisFileUnreadable, match="another host"):
        list(GisFile(key="club_points", club="testclub", type="points_of_interest").rows({}))
