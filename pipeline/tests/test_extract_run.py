"""extract/_run.py and extract/_warehouse.py end to end: real dlt, a local raw store, mocked ArcGIS servers.

Each test runs the lane the way CI and a scheduled job would - change checks,
extract, normalize, the run check, the load, the after-run check, the run log -
into a `file://` raw store under tmp_path, with requests_mock answering as an
ArcGIS Online layer does (a 304 when the layer has not moved, a
`returnCountOnly` count, pages of GeoJSON). Nothing reaches the network:
conftest.py's socket guard stays on.

The cases are the ones pipeline/ELT.md says a full reload must get right on a
safety table: an unchanged layer is skipped and keeps its rows; every closure
lifted reads as an empty table only with the server's own zero beside it; an
empty answer without that proof is refused and the last good rows stay what
the warehouse reads; a table that halves is refused.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import duckdb
import pytest
from dlt.pipeline.exceptions import PipelineStepFailed

from extract import _kinds, _run
from extract._contract import Resource
from extract._kinds import (
    ArcgisLayer,
    BucketListing,
    ClubPdf,
    GuidePages,
    HydrographyWatch,
    NwsAlerts,
    OpentrailFeed,
    PodcastFeed,
    PublishedHikes,
    ReviewedFile,
    SocrataDataset,
    WordpressPosts,
    WordpressTerms,
    catalogue_row,
    reviewed_input,
)
from extract._run import ExtractRefused, Planned, make_pipeline, run_check, run_pipeline
from extract._warehouse import load_warehouse
from fetch_opentrail import API_URL as OPENTRAIL_API_URL
from lib.freshness_state import Freshness
from lib.nws_alerts import ALERTS_URL as NWS_ALERTS_URL
from lib.user_agent import USER_AGENT
from tests.test_fetch_nynjtc_long_path_guide import INDEX, section_page
from tests.test_lib_club_pdfs import PAGE_1, PAGE_2
from tests.test_lib_hikefinder import GPX, page

AGOL = "https://services1.arcgis.com/orgid/arcgis/rest/services"
LINES_URL = f"{AGOL}/Trails/FeatureServer/0"
CLOSURES_URL = f"{AGOL}/Closures/FeatureServer/0"
ONPREM_URL = "https://gis.example.gov/arcgis/rest/services/assets/MapServer/3"
FEED_URL = "https://feeds.example.org/show.xml"
SOCRATA = "https://data.example.gov/resource/abcd-1234"
WP = "https://club.example.org/wp-json/wp/v2"
GUIDE = "https://club.example.org/guide/"
HIKES = "https://hikes.example.org/hikefinder/"
PDF_URL = "https://club.example.org/wp-content/uploads/water.pdf"
HYDRO_URL = "https://3dhp.example.gov/arcgis/rest/services/all/FeatureServer/50/query"
GREENWAY_WHERE = "status='Current' AND grnwy='Greenway'"
FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel><title>A Trail Show</title><link>https://example.org/show</link>
<item><title>Founding the Trail</title><guid>g-1</guid><pubDate>Tue, 07 May 2024 10:15:00 +0000</pubDate>
<enclosure url="https://example.org/1.mp3" length="39549437" type="audio/mpeg"/><itunes:duration>34:00</itunes:duration></item>
<item><title>Give Me Shelter</title><guid>g-2</guid><pubDate>Tue, 30 Apr 2024 10:15:00 +0000</pubDate></item>
</channel></rss>"""

FIELDS = [
    {"name": "OBJECTID", "type": "esriFieldTypeOID"},
    {"name": "GlobalID", "type": "esriFieldTypeGlobalID"},
    {"name": "NAME", "type": "esriFieldTypeString"},
    {"name": "EDITED", "type": "esriFieldTypeDate"},
    {"name": "CAPACITY", "type": "esriFieldTypeInteger"},
    {"name": "RANGER", "type": "esriFieldTypeString"},
]


class FakeLayer:
    """One ArcGIS Online layer: metadata with an ETag and 304s, a count, and pages capped at `max_records`."""

    def __init__(self, requests_mock, url, features, *, etag="v1", max_records=2, count_fails=False):
        self.url, self.features, self.etag = url, features, etag
        self.max_records, self.count_fails = max_records, count_fails
        requests_mock.get(url, json=self.metadata)
        requests_mock.get(url + "/query", json=self.query)

    def metadata(self, request, context):
        if request.headers.get("If-None-Match") == self.etag:
            context.status_code = 304
            return None
        context.headers["ETag"] = self.etag
        return {"objectIdField": "OBJECTID", "fields": FIELDS}

    def query(self, request, context):
        params = {key.lower(): value[0] for key, value in request.qs.items()}
        if params.get("returncountonly") == "true":
            if self.count_fails:
                return {"error": {"code": 500, "message": "Unable to complete operation"}}
            return {"count": len(self.features)}
        offset = int(params["resultoffset"])
        size = min(int(params["resultrecordcount"]), self.max_records)
        return {"type": "FeatureCollection", "features": self.features[offset : offset + size]}


def feature(oid, name="Trail", ranger=None):
    properties = {"OBJECTID": oid, "GlobalID": f"g{oid}", "NAME": name, "EDITED": 1790000000000, "CAPACITY": None}
    if ranger:
        properties["RANGER"] = ranger
    return {"type": "Feature", "properties": properties, "geometry": {"type": "Point", "coordinates": [-74.0, 42.0]}}


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding the test layers, in place of the real one."""
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps(
            {
                "sources": [
                    {"key": "trails", "url": LINES_URL},
                    {"key": "closures_layer", "url": CLOSURES_URL},
                    {"key": "onprem_dated", "url": ONPREM_URL, "freshness": {"kind": "arcgis_max_field", "field": "UPDATED"}},
                    {"key": "onprem_undated", "url": ONPREM_URL},
                    {"key": "a_podcast", "url": FEED_URL, "kind": "podcast_feed"},
                    {"key": "alerts", "url": "https://club.example.org/category/trail-alerts/", "kind": "published_notices"},
                    {"key": "nynjtc_long_path_guide", "url": GUIDE, "kind": "guide_pages"},
                    {"key": "hikes", "url": HIKES, "kind": "published_hikes"},
                    {"key": "gatc_water_sources", "url": PDF_URL, "kind": "club_pdf"},
                    {
                        "key": "usgs_3dhp",
                        "url": "https://3dhp.example.gov/arcgis/rest/services/all/FeatureServer",
                        "kind": "watched_only",
                        "freshness": {"kind": "arcgis_distinct_values", "url": HYDRO_URL},
                    },
                    {
                        "key": "greenways",
                        "url": "https://data.example.gov/d/abcd-1234",
                        "kind": "socrata_geojson_layer",
                        "domain": "data.example.gov",
                        "dataset_id": "abcd-1234",
                        "where": GREENWAY_WHERE,
                    },
                ]
            }
        )
    )
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


def store_root(store):
    from urllib.parse import urlparse

    return Path(urlparse(store["bucket_url"]).path)


def lane(store, *resources):
    return run_pipeline("hourly", store["bucket_url"], resources=list(resources), pipelines_dir=store["pipelines_dir"])


def warehouse(store):
    con = duckdb.connect()
    counts = load_warehouse(con, make_pipeline("hourly", store["bucket_url"], store["pipelines_dir"]))
    return con, counts


# The hourly lane carries closures, so the tests type both resources as closures and
# give the line layer an hourly override, with the reason the layout test requires.
def lines():
    return ArcgisLayer(key="trails", club="testclub", type="trail_lines", cadence_override="hourly", cadence_reason="a test")


def closures():
    return ArcgisLayer(key="closures_layer", club="testclub", type="closures")


def test_a_first_run_loads_every_table_and_the_warehouse_reads_it(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2), feature(3)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10, "Bridge out"), feature(11, "Reroute")])

    report = lane(store, lines(), closures())

    assert report.outcome == "loaded"
    assert report.rows == {"raw_testclub__trails": 3, "raw_testclub__closures_layer": 2}
    assert report.proofs == {"raw_testclub__trails": 3, "raw_testclub__closures_layer": 2}
    con, counts = warehouse(store)
    assert counts == {"raw_testclub__trails": 3, "raw_testclub__closures_layer": 2}
    columns = {row[0] for row in con.execute("describe raw.raw_testclub__trails").fetchall()}
    assert {"objectid", "globalid", "name", "edited", "geometry", "_loaded_at"} <= columns
    # CAPACITY is null on every row and exists anyway, because the layer's own fields hint it.
    assert "capacity" in columns
    # The geometry lands as GeoJSON text and round-trips into a real geometry, as a base model reads it.
    con.execute("INSTALL spatial; LOAD spatial;")
    (point,) = con.execute(
        "select st_astext(st_geomfromgeojson(geometry::varchar)) from raw.raw_testclub__trails limit 1"
    ).fetchone()
    assert point == "POINT (-74 42)"
    runs = con.execute("select table_name, verdict, outcome, rows from raw._extract_runs order by table_name").fetchall()
    assert runs == [
        ("raw_testclub__closures_layer", "stale", "loaded", 2),
        ("raw_testclub__trails", "stale", "loaded", 3),
    ]


def test_an_unchanged_layer_is_skipped_and_its_rows_are_still_what_the_warehouse_reads(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2), feature(3)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    lane(store, lines(), closures())

    second = lane(store, lines(), closures())

    assert second.verdicts == {"raw_testclub__trails": "fresh", "raw_testclub__closures_layer": "fresh"}
    assert second.load_id is None
    _, counts = warehouse(store)
    assert counts == {"raw_testclub__trails": 3, "raw_testclub__closures_layer": 1}


def test_every_closure_lifted_loads_as_an_empty_table_beside_the_servers_own_zero(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    layer = FakeLayer(requests_mock, CLOSURES_URL, [feature(10), feature(11)])
    lane(store, lines(), closures())

    layer.features, layer.etag = [], "v2"
    report = lane(store, lines(), closures())

    assert report.outcome == "loaded"
    assert report.rows["raw_testclub__closures_layer"] == 0
    assert report.proofs["raw_testclub__closures_layer"] == 0
    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 0, "a lifted closure leaves by its absence"


def test_an_empty_answer_with_no_count_is_refused_and_the_last_good_closures_stay(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    layer = FakeLayer(requests_mock, CLOSURES_URL, [feature(10), feature(11)])
    lane(store, lines(), closures())

    layer.features, layer.etag, layer.count_fails = [], "v2", True
    with pytest.raises(ExtractRefused, match="no upstream count"):
        lane(store, lines(), closures())

    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 2, "a failed fetch must never read as no closures"
    layer.count_fails = False
    retry = lane(store, lines(), closures())
    assert retry.verdicts["raw_testclub__closures_layer"] == "stale", "the refused run advanced no marker"


def test_a_trail_layer_that_halves_is_refused(registry, store, requests_mock):
    layer = FakeLayer(requests_mock, LINES_URL, [feature(i) for i in range(1, 7)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    lane(store, lines(), closures())

    layer.features, layer.etag = [feature(1), feature(2)], "v2"
    with pytest.raises(ExtractRefused, match="below the 50% floor"):
        lane(store, lines(), closures())
    _, counts = warehouse(store)
    assert counts["raw_testclub__trails"] == 6


def test_a_read_shorter_than_the_servers_count_fails_before_anything_loads(registry, store, requests_mock):
    layer = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2), feature(3)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    real_query = layer.query

    def short_query(request, context):
        answer = real_query(request, context)
        if "features" in answer and int(request.qs["resultoffset"][0]) >= 2:
            return {"type": "FeatureCollection", "features": []}
        if "count" in answer:
            return {"count": 3}
        return answer

    requests_mock.get(LINES_URL + "/query", json=short_query)
    with pytest.raises(Exception, match="the server counts 3 features and 2 were read"):
        lane(store, lines(), closures())


def test_person_fields_never_reach_a_row_or_a_column_hint(registry, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1, ranger="A. Person")])
    resource = lines()
    rows = list(resource.rows({}))
    assert "RANGER" not in rows[0]
    asked = [r.qs["outfields"][0] for r in requests_mock.request_history if "outfields" in r.qs]
    assert asked and all("ranger" not in fields.split(",") for fields in asked), "never asked for, not only dropped"
    assert all(r.headers["User-Agent"] == USER_AGENT for r in requests_mock.request_history)
    assert "RANGER" not in resource.column_hints()
    assert resource.column_hints()["EDITED"] == {"data_type": "bigint"}, "ArcGIS dates stay epoch milliseconds"


def test_an_onprem_layer_with_no_maintained_date_is_always_read(registry, requests_mock):
    resource = ArcgisLayer(key="onprem_undated", club="testclub", type="trail_lines")
    assert resource.platform == "onprem"
    assert resource.change_check({"n": "1", "max_oid": "1", "max_date": "1"}) == (Freshness.UNKNOWN, None)


def test_an_onprem_fingerprint_sees_a_delete_that_the_edit_date_alone_would_miss(registry, requests_mock):
    requests_mock.get(ONPREM_URL, json={"objectIdField": "OBJECTID"})
    answer = {"features": [{"attributes": {"n": 315, "max_oid": 900, "max_date": 1790000000000}}]}
    requests_mock.get(ONPREM_URL + "/query", json=answer)
    resource = ArcgisLayer(key="onprem_dated", club="testclub", type="points_of_interest")

    verdict, marker = resource.change_check(None)
    assert verdict is Freshness.STALE
    assert resource.change_check(marker) == (Freshness.FRESH, marker)

    answer["features"][0]["attributes"]["n"] = 314  # a lean-to deleted: the newest edit date does not move
    assert resource.change_check(marker)[0] is Freshness.STALE


def test_a_change_check_that_errors_is_unknown_and_fetches(registry, requests_mock):
    requests_mock.get(LINES_URL, status_code=503)
    assert lines().change_check({"etag": "v1"}) == (Freshness.UNKNOWN, None)


def test_run_check_wants_one_org_row_per_club(registry):
    resource = catalogue_row()
    planned = [
        Planned(resource.__class__(key=resource.key, club=club, type="org"), Freshness.STALE, None, None) for club in ("a", "b")
    ]
    assert run_check(planned, {"raw_extract__orgs": 1}, {}, {}) == [
        "raw_extract__orgs: 1 rows for 2 club folders; each org.py is exactly one"
    ]
    assert run_check(planned, {"raw_extract__orgs": 2}, {}, {}) == []


def test_run_check_refuses_an_empty_table_whose_type_may_not_be_empty():
    resource = Resource(key="k", club="c", type="points_of_interest")
    assert run_check([Planned(resource, Freshness.STALE, None, None)], {}, {"raw_c__k": 0}, {}) == [
        "raw_c__k: 0 rows, and a points_of_interest table may not be empty"
    ]


def test_atcs_reviewed_trail_updates_load_as_rows_with_the_review_beside_each():
    resource = reviewed_input("atc_trail_updates", rows_key="updates")
    resource = resource.__class__(**{**resource.__dict__, "club": "atc", "type": "closures"})
    proofs = {}
    rows = list(resource.rows(proofs))
    document = json.loads(resource.file.read_text())
    assert len(rows) == len(document["updates"]) == proofs["raw_atc__atc_trail_updates"]
    assert rows[0]["_file"]["reviewed_at"] == document["reviewed_at"]
    assert "_README" not in rows[0]["_file"]
    verdict, marker = resource.change_check(None)
    assert verdict is Freshness.STALE
    assert resource.change_check(marker)[0] is Freshness.FRESH


def test_a_reviewed_file_that_is_missing_is_unknown_not_empty(tmp_path):
    resource = ReviewedFile(key="reference/gone.json", path="reference/gone.json", club="c", type="points_of_interest")
    assert resource.change_check(None) == (Freshness.UNKNOWN, None)


def test_the_org_row_carries_the_licence_of_every_key_the_club_claims():
    resource = catalogue_row()
    resource = resource.__class__(key=resource.key, club="nysdec", type="org")
    (row,) = list(resource.rows({}))
    assert row["slug"] == "nysdec"
    claims = {claim["key"]: claim for claim in row["claims"]}
    assert claims["dec_lean_tos"]["type"] == "points_of_interest"
    assert claims["dec_lean_tos"]["reaches_hikers"] is True
    assert set(claims) == {
        "dec_hiking_trails",
        "dec_lean_tos",
        "dec_primitive_campsites",
        "dec_scenic_vistas",
        "dec_firetowers",
        "dec_viewing_areas",
        "dec_parking_areas",
        "dec_backcountry_features",
    }


def test_a_note_past_its_recheck_date_is_overdue():
    from extract._contract import NotAvailable

    note = NotAvailable(confirmed=date(2026, 1, 1), checked=("x",), where=("https://example.org",), recheck_after_days=30)
    assert note.overdue(date(2026, 3, 1))
    assert not note.overdue(date(2026, 1, 15))


def test_a_podcast_feed_lands_one_row_per_episode_and_never_the_audio(registry, requests_mock):
    requests_mock.get(FEED_URL, content=FEED, headers={"ETag": 'W/"v1"'})
    feed = PodcastFeed(key="a_podcast", club="testclub", type="podcasts")
    proofs = {}
    rows = list(feed.rows(proofs))
    assert [row["guid"] for row in rows] == ["g-1", "g-2"]
    assert proofs["raw_testclub__a_podcast"] == 2
    assert rows[0]["show_title"] == "A Trail Show"
    assert rows[0]["itunes_duration"] == "34:00"
    assert rows[0]["enclosure_url"] == "https://example.org/1.mp3"
    assert not any(r.url.endswith(".mp3") for r in requests_mock.request_history), "audio is linked, never fetched"


def test_an_unchanged_podcast_feed_answers_304_and_is_fresh(registry, requests_mock):
    def answer(request, context):
        if request.headers.get("If-None-Match") == 'W/"v1"':
            context.status_code = 304
            return b""
        context.headers["ETag"] = 'W/"v1"'
        return FEED

    requests_mock.get(FEED_URL, content=answer)
    feed = PodcastFeed(key="a_podcast", club="testclub", type="podcasts")
    verdict, marker = feed.change_check(None)
    assert verdict is Freshness.STALE
    assert feed.change_check(marker) == (Freshness.FRESH, marker)


class FakeSocrata:
    """One Socrata dataset: `count(*)` and `max(:updated_at)` under a `where`, and GeoJSON pages ordered on `:id`."""

    def __init__(self, requests_mock, rows, *, updated="2026-09-16T20:43:14.951Z", count=None):
        self.rows, self.updated, self.count = rows, updated, count
        requests_mock.get(SOCRATA + ".json", json=self.soql)
        requests_mock.get(SOCRATA + ".geojson", json=self.pages)

    def soql(self, request, context):
        assert request.qs["$where"] == [GREENWAY_WHERE.lower()], "every request carries the entry's own where"
        n = len(self.rows) if self.count is None else self.count
        return [{"n": str(n), "updated": self.updated}]

    def pages(self, request, context):
        assert request.qs["$where"] == [GREENWAY_WHERE.lower()]
        offset, limit = int(request.qs["$offset"][0]), int(request.qs["$limit"][0])
        features = [
            {
                "type": "Feature",
                "properties": {"segmentid": n, ":id": f"row-{n}"},
                "geometry": {"type": "Point", "coordinates": [-73.9, 40.7]},
            }
            for n in self.rows[offset : offset + limit]
        ]
        return {"type": "FeatureCollection", "features": features}


def greenways():
    return SocrataDataset(key="greenways", club="testclub", type="trail_lines")


def test_a_socrata_dataset_lands_its_filtered_rows_with_the_portals_count_as_proof(registry, requests_mock):
    FakeSocrata(requests_mock, [1, 2, 3])
    proofs = {}
    rows = list(greenways().rows(proofs))
    assert [row["segmentid"] for row in rows] == [1, 2, 3]
    assert [row["_socrata_id"] for row in rows] == ["row-1", "row-2", "row-3"]
    assert ":id" not in rows[0]
    assert proofs["raw_testclub__greenways"] == 3
    assert all(r.headers["User-Agent"] == USER_AGENT for r in requests_mock.request_history)


def test_a_socrata_read_shorter_than_the_portals_count_raises(registry, requests_mock):
    FakeSocrata(requests_mock, [1, 2], count=3)
    with pytest.raises(RuntimeError, match="counts 3 rows and 2 were read"):
        list(greenways().rows({}))


def test_a_socrata_marker_moves_with_the_filtered_rows_and_keeps_the_where(registry, requests_mock):
    fake = FakeSocrata(requests_mock, [1, 2, 3])
    verdict, marker = greenways().change_check(None)
    assert verdict is Freshness.STALE
    assert marker == {"n": "3", "max_updated_at": "2026-09-16T20:43:14.951Z", "where": GREENWAY_WHERE}
    assert greenways().change_check(marker) == (Freshness.FRESH, marker)
    fake.rows = [1, 2]  # a delete moves no date, and lowers the count
    assert greenways().change_check(marker)[0] is Freshness.STALE
    assert greenways().change_check({**marker, "where": "status='Current'"})[0] is Freshness.STALE


def test_a_socrata_change_check_that_errors_is_unknown(registry, requests_mock):
    requests_mock.get(SOCRATA + ".json", status_code=503)
    assert greenways().change_check(None) == (Freshness.UNKNOWN, None)


def wp_post(number, modified="2026-09-01T00:00:00"):
    return {
        "id": number,
        "slug": f"alert-{number}",
        "modified_gmt": modified,
        "link": f"https://club.example.org/alert-{number}/",
        "title": {"rendered": f"Alert {number}"},
        "content": {"rendered": "<p>The bridge is out.</p>"},
        "author": 7,
        "yoast_head_json": {"author": "A. Person"},
        "trail": [11],
    }


class FakeWordpress:
    """One WordPress site: a category found by slug, its posts with `X-WP-Total`, and taxonomy routes."""

    def __init__(self, requests_mock, posts, terms=None):
        self.posts = posts
        requests_mock.get(WP + "/categories", json=[{"id": 6, "slug": "trail-alerts"}])
        requests_mock.get(WP + "/posts", json=self.answer)
        for taxonomy, items in (terms or {}).items():
            requests_mock.get(f"{WP}/{taxonomy}", json=items, headers={"X-WP-Total": str(len(items))})

    def answer(self, request, context):
        assert request.qs["categories"] == ["6"], "posts are asked for by the category id the slug resolved to"
        size, page = int(request.qs["per_page"][0]), int(request.qs["page"][0])
        pages = max(1, -(-len(self.posts) // size))
        if page > pages:
            context.status_code = 400
            return {"code": "rest_post_invalid_page_number"}
        context.headers["X-WP-Total"] = str(len(self.posts))
        context.headers["X-WP-TotalPages"] = str(pages)
        posts = self.posts[(page - 1) * size : page * size]
        if "_fields" in request.qs:
            return [{name: post[name] for name in ("id", "modified_gmt", "slug")} for post in posts]
        return posts


def alerts():
    return WordpressPosts(key="alerts", club="testclub", type="closures")


def terms():
    return WordpressTerms(
        key="alerts", club="testclub", type="closures", taxonomies=("trail",), cadence_override="daily", cadence_reason="a test"
    )


def test_wordpress_posts_land_with_the_sites_total_and_without_the_person_fields(registry, requests_mock):
    FakeWordpress(requests_mock, [wp_post(1), wp_post(2)])
    proofs = {}
    rows = list(alerts().rows(proofs))
    assert [row["slug"] for row in rows] == ["alert-1", "alert-2"]
    assert proofs["raw_testclub__alerts"] == 2
    assert not {"author", "yoast_head_json"} & set(rows[0]), "a post's author never loads, by id or by name"
    assert rows[0]["trail"] == [11], "the taxonomy ids land; dbt resolves them against the terms table"
    assert all(r.headers["User-Agent"] == USER_AGENT for r in requests_mock.request_history)


def test_a_wordpress_marker_moves_when_a_post_is_edited_or_unpublished(registry, requests_mock):
    site = FakeWordpress(requests_mock, [wp_post(1), wp_post(2)])
    verdict, marker = alerts().change_check(None)
    assert verdict is Freshness.STALE and marker["total"] == "2"
    assert alerts().change_check(marker) == (Freshness.FRESH, marker)
    site.posts = [wp_post(1), wp_post(2, modified="2026-09-30T12:00:00")]
    assert alerts().change_check(marker)[0] is Freshness.STALE
    site.posts = [wp_post(1)]  # a lifted closure is a post taken down
    assert alerts().change_check(marker)[0] is Freshness.STALE


def test_wordpress_terms_are_their_own_daily_table_and_an_empty_vocabulary_is_refused(registry, requests_mock):
    FakeWordpress(requests_mock, [], {"trail": [{"id": 11, "name": "Allis Trail", "slug": "allis-trail", "count": 1}]})
    resource = terms()
    proofs = {}
    assert list(resource.rows(proofs)) == [
        {"id": 11, "name": "Allis Trail", "slug": "allis-trail", "count": 1, "taxonomy": "trail"}
    ]
    assert resource.table == "raw_testclub__alerts_terms" and resource.part == "terms"
    assert resource.cadence == "daily" and proofs[resource.table] == 1
    requests_mock.get(WP + "/trail", json=[], headers={"X-WP-Total": "0"})
    with pytest.raises(RuntimeError, match="came back empty"):
        list(terms().rows({}))


def test_a_daily_resource_rides_the_hourly_lane_once_a_day(registry, store, requests_mock, monkeypatch):
    FakeWordpress(requests_mock, [], {"trail": [{"id": 11, "name": "Allis Trail", "slug": "allis-trail", "count": 1}]})
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    clock = {"now": _run.utc_now_naive()}
    monkeypatch.setattr(_run, "utc_now_naive", lambda: clock["now"])
    first = lane(store, closures(), terms())
    assert set(first.verdicts) == {"raw_testclub__closures_layer", "raw_testclub__alerts_terms"}
    clock["now"] += timedelta(hours=1)
    second = lane(store, closures(), terms())
    assert set(second.verdicts) == {"raw_testclub__closures_layer"}, "checked an hour ago, so not due"
    clock["now"] += timedelta(hours=24)
    third = lane(store, closures(), terms())
    assert "raw_testclub__alerts_terms" in third.verdicts
    con, counts = warehouse(store)
    assert counts["raw_testclub__alerts_terms"] == 1


def test_a_guide_lands_one_row_per_section_and_a_page_that_stops_parsing_raises(registry, requests_mock, monkeypatch):
    monkeypatch.setattr(_kinds, "GUIDE_THROTTLE_SECONDS", 0)
    requests_mock.get(GUIDE, text=INDEX)
    requests_mock.get("https://www.nynjtc.org/lp-section-1/", text=section_page(1))
    requests_mock.get("https://www.nynjtc.org/lp-section-2/", text=section_page(2))
    guide = GuidePages(key="nynjtc_long_path_guide", club="testclub", type="points_of_interest")
    proofs = {}
    rows = list(guide.rows(proofs))
    assert [row["number"] for row in rows] == [1, 2] and proofs[guide.table] == 2
    assert all(len(row["page_sha256"]) == 64 for row in rows)
    requests_mock.get("https://www.nynjtc.org/lp-section-2/", text="<main>a page in a new shape</main>")
    with pytest.raises(ValueError):
        list(guide.rows({}))


def test_the_hike_finder_lands_each_hike_with_its_track_as_served(registry, requests_mock, monkeypatch):
    monkeypatch.setattr(_kinds, "HIKEFINDER_THROTTLE_SECONDS", 0)
    monkeypatch.delenv("HIKEFINDER_PASSWORD", raising=False)
    listing = 'Results (2 hikes found) <a href="hike.php?id=1">a</a><a href="hike.php?id=2">b</a>'
    requests_mock.get(HIKES + "hikes.php", text=listing)
    requests_mock.get(HIKES + "hike.php?id=1", text=page(gpx=True))
    requests_mock.get(HIKES + "hike.php?id=2", text=page(title="Bear Mountain Loop"))
    requests_mock.get(HIKES + "download_gpx.php?id=1", text=GPX)
    hikes = PublishedHikes(key="hikes", club="testclub", type="suggested_hikes")
    proofs = {}
    rows = list(hikes.rows(proofs))
    assert proofs[hikes.table] == 2 and len(rows) == 2
    assert rows[0]["gpx"] == GPX and rows[1]["gpx"] is None
    assert not any(r.method == "POST" for r in requests_mock.request_history), "no password set, so none is sent"


def test_a_hike_finder_listing_that_links_nothing_or_miscounts_raises(registry, requests_mock, monkeypatch):
    monkeypatch.setattr(_kinds, "HIKEFINDER_THROTTLE_SECONDS", 0)
    monkeypatch.delenv("HIKEFINDER_PASSWORD", raising=False)
    hikes = PublishedHikes(key="hikes", club="testclub", type="suggested_hikes")
    requests_mock.get(HIKES + "hikes.php", text="<form>password</form>")
    with pytest.raises(RuntimeError, match="no HIKEFINDER_PASSWORD was set"):
        list(hikes.rows({}))
    requests_mock.get(HIKES + "hikes.php", text='Results (3 hikes found) <a href="hike.php?id=1">a</a>')
    with pytest.raises(RuntimeError, match="says 3 hikes and links 1"):
        list(hikes.rows({}))


def test_a_category_of_exactly_one_full_page_never_asks_for_the_page_past_it(registry, requests_mock):
    FakeWordpress(requests_mock, [wp_post(n) for n in range(1, 101)])
    proofs = {}
    assert len(list(alerts().rows(proofs))) == 100 and proofs["raw_testclub__alerts"] == 100
    asked = [r.qs.get("page") for r in requests_mock.request_history if r.path.endswith("/posts")]
    assert asked == [["1"]], "page 2 would be a 400 from the posts route"


def water():
    return ClubPdf(key="gatc_water_sources", club="testclub", type="points_of_interest")


def test_a_club_pdf_lands_its_parsed_rows_each_with_the_documents_manifest(registry, requests_mock, monkeypatch):
    monkeypatch.setattr(_kinds, "extract_page_texts", lambda body: [PAGE_1, PAGE_2])
    requests_mock.get(
        PDF_URL, content=b"%PDF-1.7 water", headers={"ETag": '"w1"', "Last-Modified": "Mon, 02 Mar 2026 00:00:00 GMT"}
    )
    rows = list(water().rows({}))
    assert [row["mile"] for row in rows] == [0.8, 7.3, 0.2, 2.8, 38.0, 80.7]
    assert rows[0]["_document"]["etag"] == '"w1"' and rows[0]["_document"]["bytes"] == 14
    assert rows[0]["_document"]["last_modified"] == "Mon, 02 Mar 2026 00:00:00 GMT", "the club's own date is in the warehouse"


def test_a_club_pdf_is_fresh_on_a_304_or_the_same_bytes_and_stale_on_new_ones(registry, requests_mock):
    def answer(request, context):
        if request.headers.get("If-None-Match") == '"w1"':
            context.status_code = 304
            return b""
        context.headers["ETag"] = '"w1"'
        return document["bytes"]

    document = {"bytes": b"%PDF-1.7 water"}
    requests_mock.get(PDF_URL, content=answer)
    verdict, marker = water().change_check(None)
    assert verdict is Freshness.STALE and marker["etag"] == '"w1"'
    assert water().change_check(marker) == (Freshness.FRESH, marker), "a 304"
    assert water().change_check({"sha256": marker["sha256"]})[0] is Freshness.FRESH, "WordPress re-served the same bytes"
    document["bytes"] = b"%PDF-1.7 water, revised"
    assert water().change_check({"sha256": marker["sha256"]})[0] is Freshness.STALE


def test_a_club_pdf_whose_layout_changed_refuses_rather_than_relabelling(registry, requests_mock, monkeypatch):
    monkeypatch.setattr(_kinds, "extract_page_texts", lambda body: ["A table in a new shape"])
    requests_mock.get(PDF_URL, content=b"%PDF-1.7 water")
    with pytest.raises(ValueError):
        list(water().rows({}))


def test_a_layer_empty_on_its_first_read_lands_as_an_empty_table_with_its_hinted_columns(registry, store, requests_mock):
    """dlt writes no file for a table's first load when it holds no rows; the proven zero must still build."""
    FakeLayer(requests_mock, CLOSURES_URL, [])
    report = lane(store, closures())
    assert report.outcome == "loaded" and report.proofs["raw_testclub__closures_layer"] == 0
    con, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 0
    columns = {row[0] for row in con.execute('describe raw."raw_testclub__closures_layer"').fetchall()}
    assert {"objectid", "globalid", "name", "geometry", "_loaded_at", "_dlt_load_id"} <= columns
    assert "ranger" not in columns, "a person field is never hinted, so it is never created"


def test_an_empty_reviewed_file_lands_as_an_empty_table(store, tmp_path):
    reviewed = tmp_path / "work.json"
    reviewed.write_text(json.dumps({"_README": ["x"], "reviewed_at": "2026-10-01", "rows": []}))
    resource = ReviewedFile(key="work", club="testclub", type="closures", path=str(reviewed), rows_key="rows")
    lane(store, resource)
    con, counts = warehouse(store)
    assert counts["raw_testclub__work"] == 0


def test_opentrail_lands_its_waypoints_without_a_single_comment(registry, requests_mock):
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "w1",
                "properties": {"title": "Spring", "icon": "w", "comments": [{"author": "A. Person"}], "commentCount": 1},
                "geometry": {"type": "Point", "coordinates": [-84.2, 34.6]},
            }
        ],
    }
    requests_mock.get(OPENTRAIL_API_URL, json=collection, headers={"ETag": '"o1"'})
    feed = OpentrailFeed(key="at", club="opentrail", type="points_of_interest")
    rows = list(feed.rows({}))
    assert feed.table == "raw_opentrail__at", "the name dbt already reads"
    assert rows == [{"title": "Spring", "icon": "w", "feature_id": "w1", "geometry": collection["features"][0]["geometry"]}]
    assert requests_mock.last_request.headers["User-Agent"] == USER_AGENT
    verdict, marker = feed.change_check(None)
    assert verdict is Freshness.STALE and marker == {"etag": '"o1"'}


def test_the_3dhp_watch_lands_each_probes_work_units_and_a_silent_box_refuses(registry, requests_mock):
    answers = iter([["NHD"], ["NHD"], ["NHD", "3DHP_MA_01"], ["NHD"], ["NHD"]])
    requests_mock.get(
        HYDRO_URL, json=lambda request, context: {"features": [{"attributes": {"workunitid": u}} for u in next(answers)]}
    )
    watch = HydrographyWatch(key="usgs_3dhp", club="usgs", type="points_of_interest")
    proofs = {}
    rows = list(watch.rows(proofs))
    assert [row["workunitids"] for row in rows] == [["NHD"], ["NHD"], ["3DHP_MA_01", "NHD"], ["NHD"], ["NHD"]]
    assert proofs["raw_usgs__usgs_3dhp"] == 5
    assert all(r.qs["returndistinctvalues"] == ["true"] for r in requests_mock.request_history)
    requests_mock.get(HYDRO_URL, json={"features": [{"attributes": {"workunitid": None}}]})
    with pytest.raises(RuntimeError, match="named no work unit"):
        list(watch.rows({}))


def nws_alert(n, *, status="Actual", message_type="Alert", geometry=None):
    """One feature in the shape /alerts/active serves, JSON-LD keys included."""
    url = f"https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.{n}"
    return {
        "id": url,
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "@id": url,
            "@type": "wx:Alert",
            "id": f"urn:oid:2.49.0.1.840.0.{n}",
            "areaDesc": "Northern Grafton",
            "geocode": {"SAME": ["033009"], "UGC": ["NHZ003"]},
            "affectedZones": ["https://api.weather.gov/zones/forecast/NHZ003"],
            "references": [],
            "sent": "2026-10-01T15:38:00-04:00",
            "status": status,
            "messageType": message_type,
            "event": "Wind Advisory",
            "ends": None,
            "instruction": None,
        },
    }


def nws_body(*features, **extra):
    return {
        "type": "FeatureCollection",
        "title": "Current watches, warnings, and advisories",
        "updated": "2026-10-01T19:38:46+00:00",
        "features": list(features),
        **extra,
    }


def nws():
    return NwsAlerts(key="alerts", club="nws", type="warnings")


def test_nws_lands_every_alert_and_leaves_test_messages_and_cancellations_to_staging(requests_mock):
    box = {"type": "Polygon", "coordinates": [[[-72, 44], [-71, 44], [-71, 45], [-72, 44]]]}
    requests_mock.get(
        NWS_ALERTS_URL,
        json=nws_body(nws_alert(1, geometry=box), nws_alert(2, status="Test"), nws_alert(3, message_type="Cancel")),
    )
    proofs = {}
    rows = list(nws().rows(proofs))
    assert nws().table == "raw_nws__alerts"
    assert [row["status"] for row in rows] == ["Actual", "Test", "Actual"], "WN01 is staging's filter, not the extract's"
    assert proofs["raw_nws__alerts"] == 3, "the body's own count is the proof"
    assert not any(name.startswith("@") for row in rows for name in row), "JSON-LD's @id is feature_id, and @type is constant"
    assert rows[0]["feature_id"] == "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.1"
    assert rows[0]["geometry"] == box and rows[1]["geometry"] is None
    assert rows[0]["collection_updated"] == "2026-10-01T19:38:46+00:00"
    assert requests_mock.last_request.headers["User-Agent"] == USER_AGENT
    assert requests_mock.last_request.headers["Accept"] == "application/geo+json"
    assert nws().change_check({"anything": 1}) == (Freshness.UNKNOWN, None), "NWS ignores both validators"


def test_a_quiet_hour_from_nws_lands_as_an_empty_warnings_table_with_every_column(store, requests_mock):
    requests_mock.get(NWS_ALERTS_URL, json=nws_body())
    report = lane(store, nws())
    assert report.outcome == "loaded" and report.proofs["raw_nws__alerts"] == 0
    con, counts = warehouse(store)
    assert counts["raw_nws__alerts"] == 0
    columns = {row[0]: row[1] for row in con.execute('describe raw."raw_nws__alerts"').fetchall()}
    assert {"id", "event", "ends", "instruction", "areadesc", "messagetype", "geometry", "feature_id"} <= set(columns)
    assert columns["sent"] == "VARCHAR", "NWS's own offset survives; staging casts"


def test_an_nws_answer_that_is_not_a_feature_collection_refuses_and_the_last_alerts_stay(store, requests_mock):
    requests_mock.get(NWS_ALERTS_URL, json=nws_body(nws_alert(1), nws_alert(2)))
    lane(store, nws())

    requests_mock.get(NWS_ALERTS_URL, json={"type": "https://api.weather.gov/problems/Unexpected", "status": 500})
    with pytest.raises(PipelineStepFailed, match="did not answer with a FeatureCollection"):
        lane(store, nws())
    _, counts = warehouse(store)
    assert counts["raw_nws__alerts"] == 2, "a changed API must never read as no warnings"

    requests_mock.get(NWS_ALERTS_URL, json=nws_body(nws_alert(3)))
    lane(store, nws())
    con, counts = warehouse(store)
    assert counts["raw_nws__alerts"] == 1, "the refused run left nothing behind for the next load to pick up"
    assert con.execute('select feature_id from raw."raw_nws__alerts"').fetchone()[0].endswith(".3")


S3_PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{contents}<IsTruncated>{truncated}</IsTruncated>{token}</ListBucketResult>"""


def s3_object(key, etag="e1", size=10):
    return (
        f"<Contents><Key>{key}</Key><LastModified>2023-11-17T17:48:41.000Z</LastModified>"
        f'<ETag>"{etag}"</ETag><Size>{size}</Size><StorageClass>STANDARD</StorageClass></Contents>'
    )


class FakeBucket:
    """A public S3 bucket answering ListObjectsV2 in pages of `page_size`, as prd-tnm.s3.amazonaws.com does."""

    def __init__(self, requests_mock, keys, *, page_size=2, drop_token=False):
        self.objects = {key: "e1" for key in keys}
        self.page_size, self.drop_token, self.prefixes = page_size, drop_token, []
        requests_mock.get("https://prd-tnm.s3.amazonaws.com/", text=self.answer)

    def answer(self, request, context):
        query = parse_qs(urlsplit(request.url).query)  # request.qs lowercases values, and keys are case-sensitive
        prefix = query["prefix"][0]
        self.prefixes.append(prefix)
        start = int(query.get("continuation-token", ["0"])[0])
        keys = sorted(k for k in self.objects if k.startswith(prefix))
        page = keys[start : start + self.page_size]
        more = start + self.page_size < len(keys)
        token = "" if not more or self.drop_token else f"<NextContinuationToken>{start + self.page_size}</NextContinuationToken>"
        contents = "".join(s3_object(k, self.objects[k]) for k in page)
        return S3_PAGE.format(contents=contents, truncated="true" if more else "false", token=token)


DEM_PREFIX = "StagedProducts/Elevation/13/TIFF/current/"


def dem_listing():
    return BucketListing(key="3dep_13_current", club="usgs", type="elevation")


def test_a_bucket_listing_walks_every_page_of_its_fetchers_prefix_and_lands_no_object(requests_mock):
    keys = [f"{DEM_PREFIX}n4{i}w074/USGS_13_n4{i}w074.{ext}" for i in range(3) for ext in ("tif", "xml")]
    bucket = FakeBucket(requests_mock, keys)
    proofs = {}
    rows = list(dem_listing().rows(proofs))
    assert dem_listing().table == "raw_usgs__3dep_13_current"
    assert [row["key"] for row in rows] == sorted(keys), "every object, the .xml beside each tile included"
    assert proofs["raw_usgs__3dep_13_current"] == 6
    assert set(bucket.prefixes) == {DEM_PREFIX}, "the prefix is fetch_elevation.py's TILE_URL_TEMPLATE up to its first {cell}"
    assert len(bucket.prefixes) == 3, "three pages of two"
    assert rows[0] == {
        "key": sorted(keys)[0],
        "size": 10,
        "etag": '"e1"',
        "last_modified": "2023-11-17T17:48:41.000Z",
        "storage_class": "STANDARD",
    }
    assert requests_mock.last_request.headers["User-Agent"] == USER_AGENT


def test_a_bucket_listing_is_fresh_until_one_object_is_replaced(requests_mock):
    keys = [f"{DEM_PREFIX}n41w074/USGS_13_n41w074.tif", f"{DEM_PREFIX}n42w074/USGS_13_n42w074.tif"]
    bucket = FakeBucket(requests_mock, keys)
    verdict, marker = dem_listing().change_check(None)
    assert verdict is Freshness.STALE and marker["objects"] == 2
    assert dem_listing().change_check(marker) == (Freshness.FRESH, marker)
    bucket.objects[keys[1]] = "e2"
    assert dem_listing().change_check(marker)[0] is Freshness.STALE, "a republished tile, under the same name and date"


def test_a_truncated_listing_with_no_continuation_token_refuses_rather_than_reading_as_the_whole_bucket(requests_mock):
    FakeBucket(requests_mock, [f"{DEM_PREFIX}n4{i}w074/t.tif" for i in range(3)], drop_token=True)
    with pytest.raises(RuntimeError, match="no continuation token"):
        list(dem_listing().rows({}))
    assert dem_listing().change_check(None) == (Freshness.UNKNOWN, None), "a check that errors fetches"


def test_the_nhd_listing_reads_lib_nhds_prefix_through_the_lane(store, requests_mock):
    keys = [f"StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_0{h}_HU4_GPKG.zip" for h in ("102", "103", "202")]
    bucket = FakeBucket(requests_mock, [*keys, "StagedProducts/Hydrography/NHD/HU4/Shape/NHD_H_0102_HU4_Shape.zip"])
    listing = BucketListing(
        key="nhd_hu4_gpkg", club="usgs", type="points_of_interest", cadence_override="hourly", cadence_reason="a test"
    )
    report = lane(store, listing)
    assert report.rows["raw_usgs__nhd_hu4_gpkg"] == 3, "the Shape folder is outside the prefix"
    assert set(bucket.prefixes) == {"StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_"}
    con, counts = warehouse(store)
    assert counts["raw_usgs__nhd_hu4_gpkg"] == 3
    assert con.execute('select sum(size) from raw."raw_usgs__nhd_hu4_gpkg"').fetchone()[0] == 30


def test_a_load_that_dies_before_it_commits_is_never_read_as_the_current_closures(registry, store, requests_mock, monkeypatch):
    """The committed-load read, held: a load that wrote files and never committed must not become what the build reads.

    dlt's filesystem destination commits a load by writing its `_dlt_loads`
    row in complete_load(); a runner that dies before that leaves the new
    Parquet beside no commit. Under `replace` the old table's files are gone
    by then, so the honest outcomes are the previous rows or a refused build,
    never the half-load (ELT.md, "A full reload that cannot empty a safety
    table").
    """
    from dlt.destinations.impl.filesystem.filesystem import FilesystemClient

    from extract._warehouse import BuildRefused

    layer = FakeLayer(requests_mock, CLOSURES_URL, [feature(10), feature(11)])
    lane(store, closures())

    layer.features, layer.etag = [feature(12)], "v2"

    def dies(self, load_id):
        raise RuntimeError("the runner went away before the load committed")

    with monkeypatch.context() as scoped:
        scoped.setattr(FilesystemClient, "complete_load", dies)
        with pytest.raises(PipelineStepFailed, match="before the load committed"):
            lane(store, closures())

    # What a glob would read: the uncommitted file, one closure where the trail has two or one.
    on_disk = [path for path in (store_root(store) / "raw").rglob("*.parquet") if "closures_layer" in str(path)]
    assert [duckdb.sql(f"select count(*) from '{path}'").fetchone()[0] for path in on_disk] == [1]
    # Measured 2026-10-01: the replace had already removed the committed load's file, so the build refuses.
    with pytest.raises(BuildRefused, match="no committed file"):
        warehouse(store)

    lane(store, closures())
    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 1, "the next good run commits and is read"
