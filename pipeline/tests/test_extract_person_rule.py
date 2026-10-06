"""One rule for the upstream fields that name a person, in every reader that lands fields it did not name.

Decision 59 and ELT.md's rule 8 ("Who may publish") say a field that names or reaches a person never loads. Review
findings PY-1 and SEC-4 of PR #1805 (dlt → dbt re-platform as one go/no-go change) found that rule written once per
reader kind, seven copies in five variants, and disagreeing: SocrataDataset and OpentrailFeed read only
PERSON_FIELDS, so a name in a Socrata row's own `person_fields` kept loading and so did a column named like a
person's; NpsContent compared the row's names in exact case; My Maps' ExtendedData landed whole; and
definition_digest() never saw a Socrata row's list, so a FRESH change check kept serving the column after the edit.

Each reader here is given an upstream field its row names in `person_fields`, spelt in another case than the
upstream's (`Inspector_Name` for `inspector_name`), and a field named like a person's that no list names
(`contact_email`, which PERSON_SHAPED reads as one). Neither may land. A name added to the row's `person_fields`
must move the resource's definition_digest(), so the next run reads the upstream again whether or not it moved.
Every server is mocked: conftest.py's socket guard stays on.
"""

from __future__ import annotations

import json

import pytest

from extract import _content, _json_apis, _kinds, _notices, _run
from extract._contract import all_resources, discover, discover_shared
from extract._gis_files import GisFile
from extract._ogc import JsonFeatures

SOCRATA_DOMAIN, SOCRATA_ID = "data.example.gov", "abcd-1234"
WP_SITE = "https://club.example.org"
NPS_AUDIO = "https://nps.example.gov/api/v1/multimedia/audio"
NPS_ALERTS = "https://nps.example.gov/api/v1/alerts"
NPS_ROADS = "https://nps.example.gov/api/v1/roadevents"
DCNR = "https://dcnr.example.gov/ParkAddresses/api/ParkAdvisory/get"
VOLCANOES = "https://volcanoes.example.gov/hans-public/api/volcano/getElevatedVolcanoes"
FEED = "https://podcast.example.org/feed.xml"
KML_URL = "https://maps.example.com/maps/d/kml?mid=abc&forcekml=1"
GEOJSON = "https://club.example.org/maps/points.geojson"
JSON_API = "https://club.example.org/api/v1/places"
LAYER = "https://services.example.org/arcgis/rest/services/Points/FeatureServer/0"

#: What a person writes in a row's `person_fields`, in another case than the upstream spells it.
LISTED = "Inspector_Name"
#: Fields that must never land: the listed one as the upstream spells it, and one PERSON_SHAPED reads as a person's.
NEVER = ("inspector_name", "contact_email")
#: The field each fixture carries that is nobody's, and must still land.
KEPT = "facility_name"

ROWS = [
    {"key": "city_fountains", "domain": SOCRATA_DOMAIN, "dataset_id": SOCRATA_ID, "kind": "socrata_geojson_layer"},
    {"key": "club_alerts", "url": f"{WP_SITE}/category/trail-alerts/", "kind": "published_notices"},
    {"key": "nps_audio", "url": NPS_AUDIO},
    {"key": "nps_alerts", "url": NPS_ALERTS, "park_codes": {"semo": ["semo"]}},
    {"key": "nps_road_events", "url": NPS_ROADS},
    {"key": "pa_dcnr_park_advisories", "url": DCNR, "park_ids": {"6219": ["laurel"]}},
    {"key": "usgs_elevated_volcanoes", "url": VOLCANOES},
    {"key": "a_podcast", "url": FEED, "kind": "podcast_feed"},
    {"key": "fmst_helene_status", "url": KML_URL},
    {"key": "club_points", "url": GEOJSON, "file_format": "geojson"},
    {"key": "club_places", "url": JSON_API, "paging": "single", "lat_field": "lat", "lon_field": "lon"},
    {"key": "club_layer", "url": LAYER},
]


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json of one row per reader kind, each naming LISTED in its `person_fields`."""
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [{**row, "person_fields": [LISTED]} for row in ROWS]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    monkeypatch.setattr(_json_apis, "POLITE_GAP_SECONDS", 0)
    monkeypatch.setattr(_json_apis, "_LAST_REQUEST_END", {})
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setenv(_json_apis.NPS_API_KEY_ENV, "test-key-not-real")
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


def upstream_fields(**extra) -> dict:
    """An upstream item's own fields: one nobody's, the listed person field and a person-shaped one."""
    return {KEPT: "Fixture Fountain", "inspector_name": "A. Person", "contact_email": "a.person@example.org", **extra}


# --- what each reader lands -----------------------------------------------------------------------------------


def socrata(requests_mock, monkeypatch):
    feature = {"type": "Feature", "id": "row-1", "geometry": None, "properties": upstream_fields()}
    monkeypatch.setattr(_kinds, "fetch_dataset_geojson", lambda *args, **kwargs: {"features": [feature]})
    monkeypatch.setattr(_kinds.SocrataDataset, "count", lambda self: 1)
    return list(_kinds.SocrataDataset(key="city_fountains", club="testcity", type="points_of_interest").rows({}))


def opentrail(requests_mock, monkeypatch):
    feature = {"type": "Feature", "id": 1, "geometry": None, "properties": upstream_fields(dbid=1)}
    requests_mock.get(_kinds.OPENTRAIL_API_URL, json={"type": "FeatureCollection", "features": [feature]})
    return list(_kinds.OpentrailFeed(key="at", club="opentrail", type="points_of_interest").rows({}))


def wordpress(requests_mock, monkeypatch):
    requests_mock.get(f"{WP_SITE}/wp-json/wp/v2/categories", json=[{"id": 6, "slug": "trail-alerts"}])
    post = {"id": 1, "slug": "bridge-out", "title": {"rendered": "Bridge out"}, **upstream_fields()}
    requests_mock.get(f"{WP_SITE}/wp-json/wp/v2/posts", json=[post], headers={"X-WP-Total": "1"})
    return list(_kinds.WordpressPosts(key="club_alerts", club="testclub", type="closures").rows({}))


def nps_content(requests_mock, monkeypatch):
    monkeypatch.setattr(_content.NpsContent, "_read_list", lambda self, headers: ([{"id": "1", **upstream_fields()}], 1))
    return list(_content.NpsContent(key="nps_audio", club="nps", type="podcasts").rows({}))


def nps_alerts(requests_mock, monkeypatch):
    alert = {"id": "alert-1", "parkCode": "semo", "title": "Fixture alert", **upstream_fields()}
    requests_mock.get(NPS_ALERTS, json={"total": "1", "data": [alert]})
    return list(_json_apis.NpsAlerts(key="nps_alerts", club="nps", type="warnings").rows({}))


def nps_road_events(requests_mock, monkeypatch):
    feature = {"type": "Feature", "geometry": None, "properties": upstream_fields(core_details={"data_source_id": "s1"})}
    requests_mock.get(NPS_ROADS, json={"type": "FeatureCollection", "features": [feature]})
    return list(_json_apis.NpsRoadEvents(key="nps_road_events", club="nps", type="warnings").rows({}))


def dcnr(requests_mock, monkeypatch):
    requests_mock.get(DCNR, json=[{"IsAlert": True, "Message": "<p>Fixture advisory</p>", **upstream_fields()}])
    return list(_json_apis.DcnrParkAdvisories(key="pa_dcnr_park_advisories", club="pasda", type="warnings").rows({}))


def volcanoes(requests_mock, monkeypatch):
    requests_mock.get(VOLCANOES, json=[{"vnum": "900001", "volcano_name": "Fixture", **upstream_fields()}])
    return list(_json_apis.UsgsElevatedVolcanoes(key="usgs_elevated_volcanoes", club="usgs", type="warnings").rows({}))


def nws(requests_mock, monkeypatch):
    feature = {"id": "urn:fixture:1", "type": "Feature", "geometry": None, "properties": upstream_fields(event="Flood Watch")}
    requests_mock.get(_kinds.NWS_ALERTS_URL, json={"type": "FeatureCollection", "features": [feature]})
    return list(_kinds.NwsAlerts(key="alerts", club="nws", type="warnings").rows({}))


def podcast_xml() -> str:
    children = "".join(f"<{name}>{value}</{name}>" for name, value in upstream_fields().items())
    return f"<rss><channel><title>Fixture Show</title><item><title>Episode 1</title>{children}</item></channel></rss>"


def podcast_feed(requests_mock, monkeypatch):
    requests_mock.get(FEED, text=podcast_xml())
    return list(_kinds.PodcastFeed(key="a_podcast", club="testclub", type="podcasts").rows({}))


def podcast_episodes(requests_mock, monkeypatch):
    requests_mock.get(FEED, text=podcast_xml())
    return list(_content.PodcastEpisodes(key="a_podcast", club="testclub", type="podcasts").rows({}))


def my_maps(requests_mock, monkeypatch):
    data = "".join(f'<Data name="{name}"><value>{value}</value></Data>' for name, value in upstream_fields().items())
    kml = (
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"<Placemark><name>Fixture Gap</name><ExtendedData>{data}</ExtendedData>"
        "<Point><coordinates>-81.7,35.7,0</coordinates></Point></Placemark></Document></kml>"
    )
    requests_mock.get(KML_URL, text=kml, headers={"Content-Type": "application/vnd.google-earth.kml+xml"})
    rows = list(_json_apis.MyMapsPlacemarks(key="fmst_helene_status", club="fmst", type="closures").rows({}))
    return [row["extended_data"] for row in rows]


def gis_file(requests_mock, monkeypatch):
    feature = {"type": "Feature", "geometry": None, "properties": upstream_fields()}
    requests_mock.get(GEOJSON, json={"type": "FeatureCollection", "features": [feature]})
    return list(GisFile(key="club_points", club="testclub", type="points_of_interest").rows({}))


def json_api(requests_mock, monkeypatch):
    requests_mock.get(JSON_API, json=[{"id": "1", "lat": 41, "lon": -74, **upstream_fields()}])
    return list(JsonFeatures(key="club_places", club="testclub", type="places").rows({}))


def arcgis(requests_mock, monkeypatch):
    fields = [{"name": "OBJECTID", "type": "esriFieldTypeOID"}] + [
        {"name": name, "type": "esriFieldTypeString"} for name in upstream_fields()
    ]
    requests_mock.get(LAYER, json={"fields": fields, "objectIdField": "OBJECTID"})
    feature = {"type": "Feature", "id": 1, "geometry": None, "properties": {"OBJECTID": 1, **upstream_fields()}}
    requests_mock.get(LAYER + "/query", json=lambda request, context: answer(request, feature))
    return list(_kinds.ArcgisLayer(key="club_layer", club="testclub", type="points_of_interest").rows({}))


def answer(request, feature) -> dict:
    """An ArcGIS query: a count, or the page at `resultOffset`, its one feature carrying only the fields asked for."""
    if request.qs.get("returncountonly") == ["true"]:
        return {"count": 1}
    if int(request.qs.get("resultoffset", ["0"])[0]) > 0:
        return {"type": "FeatureCollection", "features": []}
    asked = request.qs.get("outfields", ["*"])[0]
    if asked == "*":
        return {"type": "FeatureCollection", "features": [feature]}
    kept = {name: value for name, value in feature["properties"].items() if name.lower() in asked.split(",")}
    return {"type": "FeatureCollection", "features": [{**feature, "properties": kept}]}


READERS = {
    "SocrataDataset": socrata,
    "OpentrailFeed": opentrail,
    "WordpressPosts": wordpress,
    "NpsContent": nps_content,
    "NpsAlerts": nps_alerts,
    "NpsRoadEvents": nps_road_events,
    "DcnrParkAdvisories": dcnr,
    "UsgsElevatedVolcanoes": volcanoes,
    "NwsAlerts": nws,
    "PodcastFeed": podcast_feed,
    "PodcastEpisodes": podcast_episodes,
    "MyMapsPlacemarks ExtendedData": my_maps,
    "GisFile": gis_file,
    "JsonFeatures": json_api,
    "ArcgisLayer": arcgis,
}


#: The two readers with no sources.json row, whose rule is PERSON_FIELDS and PERSON_SHAPED alone: the listed name
#: is nobody's list there, so only the person-shaped field must stay out.
ROWLESS = frozenset({"OpentrailFeed", "NwsAlerts"})


@pytest.mark.parametrize("kind", READERS)
def test_a_field_the_row_lists_in_any_case_and_a_person_shaped_field_never_land_from_any_reader(
    registry, requests_mock, monkeypatch, kind
):
    rows = READERS[kind](requests_mock, monkeypatch)
    never = {"contact_email"} if kind in ROWLESS else set(NEVER)

    assert rows, "the fixture lands a row"
    for row in rows:
        landed = {name.lower() for name in row}
        assert KEPT in landed, "a field that is nobody's still lands"
        assert not landed & never, f"{sorted(landed & never)} landed"


# --- the marker's digest --------------------------------------------------------------------------------------

KEYED = {
    "SocrataDataset": lambda: _kinds.SocrataDataset(key="city_fountains", club="testcity", type="points_of_interest"),
    "WordpressPosts": lambda: _kinds.WordpressPosts(key="club_alerts", club="testclub", type="closures"),
    "NpsContent": lambda: _content.NpsContent(key="nps_audio", club="nps", type="podcasts"),
    "NpsAlerts": lambda: _json_apis.NpsAlerts(key="nps_alerts", club="nps", type="warnings"),
    "NpsRoadEvents": lambda: _json_apis.NpsRoadEvents(key="nps_road_events", club="nps", type="warnings"),
    "DcnrParkAdvisories": lambda: _json_apis.DcnrParkAdvisories(key="pa_dcnr_park_advisories", club="pasda", type="warnings"),
    "UsgsElevatedVolcanoes": lambda: _json_apis.UsgsElevatedVolcanoes(
        key="usgs_elevated_volcanoes", club="usgs", type="warnings"
    ),
    "PodcastFeed": lambda: _kinds.PodcastFeed(key="a_podcast", club="testclub", type="podcasts"),
    "PodcastEpisodes": lambda: _content.PodcastEpisodes(key="a_podcast", club="testclub", type="podcasts"),
    "MyMapsPlacemarks": lambda: _json_apis.MyMapsPlacemarks(key="fmst_helene_status", club="fmst", type="closures"),
    "GisFile": lambda: GisFile(key="club_points", club="testclub", type="points_of_interest"),
    "JsonFeatures": lambda: JsonFeatures(key="club_places", club="testclub", type="places"),
    "ArcgisLayer": lambda: _kinds.ArcgisLayer(key="club_layer", club="testclub", type="points_of_interest"),
}


@pytest.mark.parametrize("build", KEYED.values(), ids=KEYED.keys())
def test_a_name_added_to_a_rows_person_fields_moves_the_digest_so_an_unmoved_upstream_is_read_again(registry, build):
    before = _run.definition_digest(build())

    sources = json.loads(registry.read_text())
    for row in sources["sources"]:
        row["person_fields"] = [*row["person_fields"], "Steward_Phone_Tree"]
    registry.write_text(json.dumps(sources))
    _kinds._registry.cache_clear()

    assert _run.definition_digest(build()) != before, "a FRESH change check would keep the column the row now names"
    assert "steward_phone_tree" in build().field_rules["person_fields"], "the reader leaves the new name out"


#: The kinds whose rows may list `person_fields` while the reader lands only columns it names itself, so a person
#: field cannot arrive and the list is the registration's record of what was read, not a rule anything applies:
#: FeedNotices keeps a title, a date, a link and a sha256 (extract/_notices.py), PageNotice its PAGE_COLUMNS.
NAMES_ITS_OWN_COLUMNS = frozenset({"FeedNotices", "PageNotice"})


def test_every_registered_reader_whose_row_lists_person_fields_carries_them_into_its_digest():
    """The registry's own rows, through discover(): a kind that keeps fields it did not name and reads its row's
    `person_fields` some other way, or not at all, is the gap PY-1 and SEC-4 found, and fails here by name."""
    missed = []
    for resource in all_resources(discover()) + all_resources(discover_shared()):
        try:
            listed = {name.lower() for name in resource.entry.get("person_fields") or ()}
        except (AttributeError, KeyError):
            continue  # a resource with no sources.json row has no list of its own
        if not listed or type(resource).__name__ in NAMES_ITS_OWN_COLUMNS:
            continue
        carried = set((getattr(resource, "field_rules", None) or {}).get("person_fields") or ())
        if not listed <= carried:
            missed.append(f"{resource.name} ({type(resource).__name__}): {sorted(listed - carried)}")
    assert not missed, "rows whose person_fields no digest sees:\n" + "\n".join(missed)
