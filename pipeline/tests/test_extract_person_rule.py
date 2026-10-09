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

import csv
import json
import re

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


# --- WordPress's plugin fields (review finding SEC-2) ---------------------------------------------------------

#: Every WordPress column a dbt model reads by name, from a grep of pipeline/dbt/models on 2026-10-06: the notices'
#: facts (`id`, `title`, `link`, `modified_gmt`), NYNJTC's base model (`slug`, `modified` and its four place
#: taxonomies), the wording union's prose (`content`, `excerpt`, `uagb_excerpt`), and, because the suggested-hike
#: staging models carry every other column in `properties`, the fields WordPress's own REST API serves and the
#: taxonomies the registered hike lists are read with (GMC's six, site_terms() in extract/gmc/suggested_hikes.py).
WORDPRESS_COLUMNS_MODELS_READ = (
    *("id", "date", "date_gmt", "modified", "modified_gmt", "slug", "status", "type", "link", "title"),
    *("content", "excerpt", "uagb_excerpt", "featured_media", "sticky", "format", "categories", "tags", "acf"),
    *("parent", "menu_order", "trail", "park", "region", "state"),
    *("difficulty", "distance", "hike-feature", "hike-status", "hike-type", "alert-category"),
)


def test_a_wordpress_plugin_field_that_names_the_author_never_lands_and_every_field_a_model_reads_still_does(
    registry, requests_mock
):
    """A theme's `author_info`, All in One SEO's REST block and a contact address are what a site's next plugin adds
    after its row was read field by field; none is in the row's `person_fields`, so only the rule can stop them."""
    requests_mock.get(f"{WP_SITE}/wp-json/wp/v2/categories", json=[{"id": 6, "slug": "trail-alerts"}])
    post = {name: f"fixture {name}" for name in WORDPRESS_COLUMNS_MODELS_READ}
    post.update(
        {
            "author_info": {"display_name": "A. Staffer", "author_link": "https://club.example.org/author/astaffer/"},
            "aioseo_head_json": {"schema": {"@graph": [{"@type": "Person", "name": "A. Staffer"}]}},
            "aioseo_head": '<meta name="author" content="A. Staffer">',
            "authors": [{"display_name": "A. Staffer"}],
            "contact_email": "a.staffer@example.org",
        }
    )
    requests_mock.get(f"{WP_SITE}/wp-json/wp/v2/posts", json=[post], headers={"X-WP-Total": "1"})

    (row,) = list(_kinds.WordpressPosts(key="club_alerts", club="testclub", type="closures").rows({}))

    assert "A. Staffer" not in json.dumps(row) and "a.staffer@example.org" not in json.dumps(row)
    assert set(row) == set(WORDPRESS_COLUMNS_MODELS_READ), "the name filter leaves out people and nothing else"


# --- a field name written with spaces, hyphens or dots ----------------------------------------------------------

#: How KML ExtendedData, a QGIS GeoJSON export or a CSV header spells a person's field, and the name dlt's sql_ci_v1
#: naming lands it under. Round-2 fix worker A of PR #1805 found that PERSON_SHAPED read the first spelling as one
#: word, so `Contact Email` landed as `contact_email`.
SPELT_APART = {
    "Contact Email": "contact_email",
    "E-mail": "e_mail",
    "Phone Number": "phone_number",
    "contact.email": "contact_email",
    "Owner  Name": "owner_name",
    "Phone#": "phone",
}


@pytest.mark.parametrize("name", SPELT_APART)
def test_a_person_shaped_field_name_written_with_spaces_hyphens_or_dots_never_loads(name):
    assert _kinds.PersonRule().left_out([name]) == {name.lower(): _kinds.SHAPED}


@pytest.mark.parametrize(
    ("listed", "upstream"),
    [
        ("trail_crew_lead", "Trail Crew Lead"),
        ("Trail Crew Lead", "trail_crew_lead"),
        ("trail_crew_lead", "Trail-Crew-Lead"),
        ("TRAIL_CREW_LEAD", "Trail Crew Lead"),
    ],
)
def test_a_rows_person_fields_match_whether_written_as_the_upstream_spells_the_name_or_as_dlt_lands_it(listed, upstream):
    rule = _kinds.PersonRule.of({"person_fields": [listed]})
    assert rule.left_out([upstream, "Trail Name"]) == {upstream.lower(): "the row's person_fields"}


@pytest.mark.parametrize(
    ("cleared", "upstream"),
    [("land_manager", "Land Manager"), ("Land Manager", "land_manager"), ("Land Manager", "LAND_MANAGER")],
)
def test_a_rows_not_person_fields_clear_a_name_whether_written_as_the_upstream_spells_it_or_as_dlt_lands_it(cleared, upstream):
    assert _kinds.PersonRule().left_out([upstream]) == {upstream.lower(): _kinds.SHAPED}, "the backstop reads it"
    assert _kinds.PersonRule.of({"not_person_fields": [cleared]}).left_out([upstream]) == {}


#: The readers whose upstream names may hold a space: JSON objects and KML ExtendedData. An RSS item's names are XML
#: tags and an ArcGIS layer's come from its field list, neither of which may.
SPACED_READERS = {kind: READERS[kind] for kind in READERS if kind not in ("PodcastFeed", "PodcastEpisodes", "ArcgisLayer")}


@pytest.mark.parametrize("kind", SPACED_READERS)
def test_a_field_name_written_with_spaces_never_lands_from_any_reader_whose_names_may_hold_one(
    registry, requests_mock, monkeypatch, kind
):
    """`Inspector Name` is the row's `Inspector_Name` (LISTED) as a spreadsheet heads it; `Contact Email` and
    `Phone Number` are names PERSON_SHAPED reads as a person's once split at the space."""
    spaced = {"Facility Name": "Fixture Fountain", "Inspector Name": "A. Person", "Contact Email": "a@example.org"}
    spaced["Phone Number"] = "555-0100"
    monkeypatch.setitem(globals(), "upstream_fields", lambda **extra: {**spaced, **extra})
    rows = SPACED_READERS[kind](requests_mock, monkeypatch)
    never = {"contact email", "phone number"} | (set() if kind in ROWLESS else {"inspector name"})

    assert rows, "the fixture lands a row"
    for row in rows:
        landed = {name.lower() for name in row}
        assert "facility name" in landed, "a field that is nobody's still lands"
        assert not landed & never, f"{sorted(landed & never)} landed"


# --- the backstop widened on 2026-10-09 -----------------------------------------------------------------------------

#: Field names PERSON_SHAPED let load until 2026-10-09, each a person's by its shape: the three decision 54's wave 6
#: found on D&L Corridor's trailheads and Montour Trail's access areas (both rows list them by hand), the 23 that
#: PR #1805's security review listed that night, the same shapes run together, cut to a shapefile's ten characters or
#: plural, as registry rows already list them by hand (OWNERNAME, entityphone, created_us), and the Buckeye Trail's
#: "Section supervisor", a volunteer's name on each section page.
NEWLY_PERSON_SHAPED = (
    *("updatedBy", "LocationBy", "MODIFIED_BY"),
    *("LastModifiedBy", "reviewed_by", "ReportedBy", "submitted_by", "approved_by", "inspected_by", "assigned_to"),
    *("CollectedBy", "MappedBy", "GPS_By", "RangerName", "first_name", "LastName", "full_name", "reporter"),
    *("submitter", "inspector", "volunteer", "overseer", "adopter", "maintainer", "mobile", "cell"),
    *("UPDATEDBY", "Round1QAQCBy", "OWNERNAME", "OWNERNME1", "MAINTAINERNAME", "created_us", "LAST_EDITE"),
    *("entityphone", "entityemail", "MGRPHONE", "contacts", "TELNO", "FAXNUMBER", "DataEntryPerson", "COLLECTOR"),
    *("TrailAdopter", "volunteers", "Section Supervisor"),
)


@pytest.mark.parametrize("name", NEWLY_PERSON_SHAPED)
def test_person_shaped_leaves_out_a_name_the_2026_10_06_word_list_let_load(name):
    assert _kinds.PersonRule().left_out([name]) == {name.lower(): _kinds.SHAPED}


#: Names beside the new shapes that are nobody's and still load: a ranger district, a reporter's type, PA DCNR's
#: MOBILE_FAC, a grid's cell_size, a shelter's capacity in persons, a count of volunteer hours, GMC's SHtype_Mgr and
#: an edit date named like an editor's field.
STILL_LOADS = (
    *("RANGER_DISTRICT", "reporter_type", "MOBILE_FAC", "cell_size", "persons", "Volunteer_Hours", "SHtype_Mgr"),
    "LocationDate",
)


@pytest.mark.parametrize("name", STILL_LOADS)
def test_person_shaped_still_loads_a_name_beside_the_new_shapes_that_is_nobodys(name):
    assert _kinds.PersonRule().left_out([name]) == {}


def test_a_layer_whose_row_lists_none_of_wave_6s_three_names_never_asks_for_them(registry, requests_mock, monkeypatch):
    """D&L Corridor's `updatedBy` and Montour Trail's `MODIFIED_BY` and `LocationBy` on a row whose `person_fields` name
    none of them: the backstop alone keeps them out of outFields, so no value crosses the wire."""
    staff = {"updatedBy": "A. Person", "MODIFIED_BY": "a.person", "LocationBy": "A. Person"}
    monkeypatch.setitem(globals(), "upstream_fields", lambda **extra: {KEPT: "Fixture Trailhead", **staff, **extra})

    rows = arcgis(requests_mock, monkeypatch)

    asked = {name for r in requests_mock.request_history if "outfields" in r.qs for name in r.qs["outfields"][0].split(",")}
    assert asked and not asked & {name.lower() for name in staff}, "never asked for, not only dropped"
    assert rows and all(set(row) == {"OBJECTID", KEPT, "geometry"} for row in rows), rows


#: Columns PERSON_SHAPED reads as a person's since 2026-10-09 that name a place or a body, each cleared in its own
#: sources.json row's `not_person_fields`: four a model reads (stg_nynjtc__long_path's `maintainer`, the generated
#: base model's key `full_name`, and two titles seeds/notice_source_fields.csv names), and four whose rows record what
#: they hold.
CLEARED_FOR_THE_WIDENED_BACKSTOP = [
    ("nynjtc_long_path", "Maintainer"),
    ("ugrc_state_park_points", "full_name"),
    ("oprd_hunting_areas", "FULL_NAME"),
    ("nps_seki_closures", "FullName"),
    ("patc_trails_master", "Maintainer"),
    ("nps_points_of_interest", "MAINTAINER"),
    ("nps_trail_of_tears_nht", "MAINTAINER"),
    ("usace_mobile_trails", "managedBy"),
]


@pytest.mark.parametrize(("key", "field"), CLEARED_FOR_THE_WIDENED_BACKSTOP)
def test_an_organisation_column_the_widened_backstop_reads_as_a_persons_still_loads_where_its_row_clears_it(key, field):
    layer = _kinds.ArcgisLayer(key=key, club="testclub", type="points_of_interest")

    assert _kinds.PersonRule().shaped(field), "the backstop alone leaves it out, so the row's clearance is what keeps it"
    assert layer.dropped_fields({"fields": [{"name": field, "type": "esriFieldTypeString"}]}) == {}


#: The columns notice_field() reads for each notice source (seeds/notice_source_fields.csv), the date columns aside.
NOTICE_SEED_COLUMNS = ("title", "category", "status", "starts", "ends", "rescinded", "link", "locality")
#: Declared fields the person rule leaves out today, each with why it stands. fta_fnst_closed_segments' `Manager_Na`
#: is the notice seed's locality, and the backstop has read it as a person's since `manager` joined the word list
#: (review finding EXD-3, 02a53b22, 2026-10-05), so that notice's locality reads null. Whether it names a person or
#: the land's managing body is unread: a person reading its values settles it, then clears it in the row, or the seed
#: stops naming it.
KNOWN_LEFT_OUT = {("fta_fnst_closed_segments", "Manager_Na")}


def declared_fields() -> list[tuple[str, str]]:
    """(row key, field) for every field a sources.json row or a seed names for a model to read."""
    from extract._contract import PIPELINE_DIR

    declared = []
    for row in json.loads((PIPELINE_DIR / "sources.json").read_text())["sources"]:
        for name, value in row.items():
            if name.endswith(("_field", "_fields")) and name not in ("person_fields", "not_person_fields"):
                declared += [(row["key"], field) for field in (value if isinstance(value, list) else [value])]
    for path in sorted((PIPELINE_DIR / "dbt" / "seeds").glob("*.csv")):
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            names = reader.fieldnames or []
            columns = NOTICE_SEED_COLUMNS if path.name == "notice_source_fields.csv" else [n for n in names if n == "field"]
            if "source_key" in names:
                declared += [(line["source_key"], line[column]) for line in reader for column in columns if line[column]]
    return [(key, field) for key, field in declared if isinstance(field, str) and field != "geometry"]


def test_no_field_a_registry_row_or_a_seed_names_for_a_model_is_one_the_person_rule_leaves_out():
    """A generated base model reads a row's name_field, key_fields and the like by name, and the notice models read the
    notice seed's columns through notice_field(), which answers null for a column that never landed rather than
    failing. So a backstop widened past one of them nulls a notice's title in silence, as the 2026-10-09 widening
    would have done to oprd_hunting_areas' and nps_seki_closures' titles had their rows not cleared them. A date
    column named like an editor's is left aside: a live ArcGIS read keeps it by its type (NEVER_PERSON_TYPES)."""
    from extract._contract import PIPELINE_DIR

    rows = {row["key"]: row for row in json.loads((PIPELINE_DIR / "sources.json").read_text())["sources"]}
    declared = declared_fields()

    left_out = {
        (key, field)
        for key, field in declared
        if not re.search(r"(^|_)date($|_)", _kinds._name_words(field)) and _kinds.PersonRule.of(rows.get(key)).left_out([field])
    }

    assert len(declared) > 1000, "the registry and the seeds were read"
    assert left_out == KNOWN_LEFT_OUT, sorted(left_out - KNOWN_LEFT_OUT)
