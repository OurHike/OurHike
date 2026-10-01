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
from datetime import date

import duckdb
import pytest

from extract import _kinds
from extract._contract import Resource
from extract._kinds import ArcgisLayer, PodcastFeed, ReviewedFile, SocrataDataset, catalogue_row, reviewed_input
from extract._run import ExtractRefused, Planned, make_pipeline, run_check, run_pipeline
from extract._warehouse import load_warehouse
from lib.freshness_state import Freshness
from lib.user_agent import USER_AGENT

AGOL = "https://services1.arcgis.com/orgid/arcgis/rest/services"
LINES_URL = f"{AGOL}/Trails/FeatureServer/0"
CLOSURES_URL = f"{AGOL}/Closures/FeatureServer/0"
ONPREM_URL = "https://gis.example.gov/arcgis/rest/services/assets/MapServer/3"
FEED_URL = "https://feeds.example.org/show.xml"
SOCRATA = "https://data.example.gov/resource/abcd-1234"
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
