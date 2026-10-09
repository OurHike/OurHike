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

import errno
import hashlib
import json
import pickle
import shutil
import tempfile
import threading
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import duckdb
import pytest
import requests
from dlt.common.storages.load_package import ParsedLoadJobFileName
from dlt.normalize.exceptions import NormalizeJobFailed
from dlt.pipeline.exceptions import PipelineStepFailed

from extract import _kinds, _notices, _run
from extract._contract import Resource
from extract._kinds import (
    MONTHLY_READ_BACKOFF_SECONDS,
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
from lib import arcgis, http_retry
from lib.freshness_state import Freshness
from lib.nws_alerts import ALERTS_URL as NWS_ALERTS_URL
from lib.user_agent import USER_AGENT
from tests.test_fetch_nynjtc_long_path_guide import INDEX, section_page
from tests.test_lib_club_pdfs import PAGE_1, PAGE_2
from tests.test_lib_hikefinder import GPX, page

AGOL = "https://services1.arcgis.com/orgid/arcgis/rest/services"
LINES_URL = f"{AGOL}/Trails/FeatureServer/0"
LINES_Z_URL = f"{AGOL}/CenterlineZ/FeatureServer/9"
UNPAGED_URL = "https://gis.example.org/arcgis/rest/services/Trail/MapServer/0"
CLOSURES_URL = f"{AGOL}/Closures/FeatureServer/0"
STATUS_URL = f"{AGOL}/SiteStatus/FeatureServer/0"
STAFFED_URL = f"{AGOL}/Waypoints/FeatureServer/1"
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


class FakeZLayer(FakeLayer):
    """A Z-enabled layer, answering as ArcGIS Online did on 2026-10-03: f=geojson drops Z even with returnZ, f=json keeps it.

    `features` are Esri JSON features with three-number vertices.
    """

    def query(self, request, context):
        params = {key.lower(): value[0] for key, value in request.qs.items()}
        if params.get("returncountonly") == "true":
            return {"count": len(self.features)}
        offset = int(params["resultoffset"])
        page = self.features[offset : offset + min(int(params["resultrecordcount"]), self.max_records)]
        if params.get("f") == "json":
            keep = 3 if params.get("returnz") == "true" else 2
            return {
                "geometryType": "esriGeometryPolyline",
                "features": [
                    {"attributes": f["attributes"], "geometry": {"paths": [[p[:keep] for p in f["geometry"]["paths"][0]]]}}
                    for f in page
                ],
            }
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": f["attributes"],
                    "geometry": {"type": "LineString", "coordinates": [p[:2] for p in f["geometry"]["paths"][0]]},
                }
                for f in page
            ],
        }


def z_feature(oid, z):
    return {
        "attributes": {"OBJECTID": oid, "NAME": "Centerline"},
        "geometry": {"paths": [[[-68.92, 45.90, z], [-68.93, 45.91, z - 9.5]]]},
    }


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
                    {"key": "centerline_z", "url": LINES_Z_URL, "return_z": True},
                    {"key": "unpaged", "url": UNPAGED_URL},
                    {"key": "closures_layer", "url": CLOSURES_URL},
                    {"key": "status_layer", "url": STATUS_URL, "where": "status = 'closed'"},
                    {
                        "key": "staffed",
                        "url": STAFFED_URL,
                        "person_fields": ["source"],
                        "not_person_fields": ["LastEdit_1", "Editor"],
                    },
                    {"key": "onprem_dated", "url": ONPREM_URL, "freshness": {"kind": "arcgis_max_field", "field": "UPDATED"}},
                    {"key": "onprem_undated", "url": ONPREM_URL},
                    {"key": "a_podcast", "url": FEED_URL, "kind": "podcast_feed"},
                    {"key": "alerts", "url": "https://club.example.org/category/trail-alerts/", "kind": "published_notices"},
                    {"key": "nynjtc_long_path_guide", "url": GUIDE, "kind": "guide_pages"},
                    {"key": "hikes", "url": HIKES, "kind": "published_hikes"},
                    {"key": "gatc_water_sources", "url": PDF_URL, "kind": "club_pdf", "crawl_delay": 10},
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
                        "crawl_delay": 1,
                    },
                ]
            }
        )
    )
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_host_gap(monkeypatch):
    """No host is asked anything, so extract/_notices.py's per-host gate waits nothing here, and starts each test empty."""
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(_notices, "_GATES", {})


@pytest.fixture
def gate_clock(monkeypatch):
    """The per-host gate on a clock that moves only when it pauses: the list of pauses it made, in order."""
    clock, pauses = {"now": 1000.0}, []

    def pause(seconds):
        pauses.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(_notices, "_now", lambda: clock["now"])
    monkeypatch.setattr(_notices, "_pause", pause)
    return pauses


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


def test_a_closures_read_cut_short_with_no_readable_count_is_refused_and_the_last_good_closures_stay(
    registry, store, requests_mock
):
    """Closures have no shrink floor, so only the server's own count can tell a short read from closures lifted."""
    layer = FakeLayer(requests_mock, CLOSURES_URL, [feature(i) for i in range(10, 16)], max_records=2)
    lane(store, closures())
    first_query = layer.query

    def cut_short(request, context):
        params = {key.lower(): value[0] for key, value in request.qs.items()}
        if params.get("returncountonly") != "true" and int(params["resultoffset"]) >= 2:
            return {"type": "FeatureCollection", "features": []}  # an empty page in place of an error
        return first_query(request, context)

    requests_mock.get(CLOSURES_URL + "/query", json=cut_short)
    layer.etag, layer.count_fails = "v2", True

    with pytest.raises(ExtractRefused, match="raw_testclub__closures_layer: 2 rows and no upstream count"):
        lane(store, closures())
    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 6


def test_run_check_refuses_a_closures_table_of_any_size_without_the_upstreams_count():
    resource = Resource(key="k", club="c", type="closures")
    planned = [Planned(resource, Freshness.STALE, None, None)]
    assert run_check(planned, {"raw_c__k": 4}, {}, {"raw_c__k": 6}) == [
        "raw_c__k: 4 rows and no upstream count read this run; a closures table has no shrink floor, "
        "so a read cut short would pass as rows removed"
    ]
    assert run_check(planned, {"raw_c__k": 4}, {"raw_c__k": 4}, {"raw_c__k": 6}) == []
    trails = [Planned(Resource(key="k", club="c", type="trail_lines"), Freshness.STALE, None, None)]
    assert run_check(trails, {"raw_c__k": 4}, {}, {"raw_c__k": 6}) == [], "the 50% floor holds a type that has one"


def test_a_store_whose_first_run_was_refused_loads_its_next_run_as_one_package_on_a_fresh_runner(registry, store, requests_mock):
    """refresh-reference.yml's monthly lane, 37058045092 then 37070628933: refused, then "2 committed"."""
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    layer = FakeLayer(requests_mock, CLOSURES_URL, [])
    layer.count_fails = True
    with pytest.raises(ExtractRefused, match="no upstream count"):
        lane(store, lines(), closures())
    shutil.rmtree(store["pipelines_dir"])  # CI's runners start with no working directory

    layer.count_fails, layer.features = False, [feature(10)]
    report = lane(store, lines(), closures())

    assert report.outcome == "loaded"
    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 1


def test_a_store_an_older_build_left_with_a_second_schema_still_loads_one_package_a_run(
    registry, store, requests_mock, monkeypatch
):
    """A refused first run's log, written as a bare resource, made the store's default schema `ourhike_<lane>`."""
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    layer = FakeLayer(requests_mock, CLOSURES_URL, [])
    layer.count_fails = True
    with monkeypatch.context() as older:
        older.setattr(_run, "store_schema", lambda pipeline: None)  # what dlt chose before store_schema()
        with pytest.raises(ExtractRefused, match="no upstream count"):
            lane(store, lines(), closures())
    shutil.rmtree(store["pipelines_dir"])
    synced = make_pipeline("hourly", store["bucket_url"], store["pipelines_dir"])
    synced.sync_destination()
    assert synced.default_schema_name == "ourhike_hourly", "the store this test exists for"

    layer.count_fails, layer.features = False, [feature(10)]
    report = lane(store, lines(), closures())

    assert report.outcome == "loaded"
    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 1


def test_a_store_whose_default_schema_is_the_pipelines_answers_an_unchanged_layer_fresh_on_a_fresh_runner(
    registry, store, requests_mock, monkeypatch
):
    """refresh-reference.yml's monthly runs 16 and 17 (37210020925, 37232256991): "0 fresh" of 545, then of 569.

    dlt keeps resource state under the extract schema's name, which in this
    store is `ourhike_<lane>`, not the source's own name `extract`.
    """
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    layer = FakeLayer(requests_mock, CLOSURES_URL, [])
    layer.count_fails = True
    with monkeypatch.context() as older:
        older.setattr(_run, "store_schema", lambda pipeline: None)  # what dlt chose before store_schema()
        with pytest.raises(ExtractRefused, match="no upstream count"):
            lane(store, lines(), closures())
    layer.count_fails, layer.features = False, [feature(10)]
    shutil.rmtree(store["pipelines_dir"])
    assert lane(store, lines(), closures()).outcome == "loaded"
    shutil.rmtree(store["pipelines_dir"])  # CI's runners start with no working directory

    second = lane(store, lines(), closures())

    assert second.verdicts == {"raw_testclub__trails": "fresh", "raw_testclub__closures_layer": "fresh"}
    assert second.load_id is None
    _, counts = warehouse(store)
    assert counts == {"raw_testclub__trails": 1, "raw_testclub__closures_layer": 1}


def test_a_load_that_committed_without_its_run_log_is_read_again_rather_than_answered_fresh(
    registry, store, requests_mock, monkeypatch
):
    """refresh-reference.yml's monthly lane: 37070628933 committed and refused before its log, then 37081046157 skipped 53."""
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])

    def dies(*args, **kwargs):
        raise RuntimeError("the runner went away after the load committed")

    with monkeypatch.context() as died:
        died.setattr(_run, "write_run_log", dies)
        with pytest.raises(RuntimeError, match="went away"):
            lane(store, lines(), closures())
    _, unlogged = warehouse(store)
    assert unlogged == {}, "the store this test exists for: committed rows that no run log names"

    report = lane(store, lines(), closures())

    assert report.verdicts == {"raw_testclub__trails": "stale", "raw_testclub__closures_layer": "stale"}
    _, counts = warehouse(store)
    assert counts == {"raw_testclub__trails": 2, "raw_testclub__closures_layer": 1}


def _run_log_dies(monkeypatch):
    def dies(*args, **kwargs):
        raise RuntimeError("the runner went away after the load committed")

    monkeypatch.setattr(_run, "write_run_log", dies)
    return RuntimeError


def _after_run_check_fails(monkeypatch):
    monkeypatch.setattr(_run, "committed", lambda *args, **kwargs: ["injected: rows on disk differ"])
    return ExtractRefused


def _dlt_loads_row_fails(monkeypatch):
    """dlt 1.30.0's FilesystemClient.complete_load() stores the state, markers included, before this row."""
    from dlt.destinations.impl.filesystem.filesystem import FilesystemClient

    def fails(self, load_id):
        raise OSError("R2 503 writing the _dlt_loads row")

    monkeypatch.setattr(FilesystemClient, "_store_load", fails)
    return PipelineStepFailed


@pytest.mark.parametrize("fresh_runner", [False, True], ids=["same runner", "fresh runner"])
@pytest.mark.parametrize("fault", [_run_log_dies, _after_run_check_fails, _dlt_loads_row_fails])
def test_a_marker_from_a_newer_unlogged_load_is_not_trusted_when_it_deleted_the_logged_loads_files(
    registry, store, requests_mock, monkeypatch, fault, fresh_runner
):
    """The newer load's `replace` deleted the logged load's files, so its marker describes rows no build can read."""
    layer = FakeLayer(requests_mock, CLOSURES_URL, [feature(10), feature(11)])
    lane(store, closures())
    layer.features, layer.etag = [feature(12)], "v2"
    with monkeypatch.context() as scoped:
        with pytest.raises(fault(scoped)):
            lane(store, closures())
    if fresh_runner:
        shutil.rmtree(store["pipelines_dir"])

    third = lane(store, closures())

    assert third.verdicts["raw_testclub__closures_layer"] == "unknown"
    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 1


def test_a_marker_from_an_unlogged_load_over_a_logged_proven_zero_is_not_trusted(registry, store, requests_mock, monkeypatch):
    """A first-run zero writes no file, so the files check alone cannot see the newer load; its own files can."""
    layer = FakeLayer(requests_mock, CLOSURES_URL, [])
    lane(store, closures())
    layer.features, layer.etag = [feature(12)], "v2"
    with monkeypatch.context() as scoped:
        with pytest.raises(_run_log_dies(scoped)):
            lane(store, closures())

    third = lane(store, closures())

    assert third.verdicts["raw_testclub__closures_layer"] == "unknown", "a FRESH here serves the logged zero: no closures"
    _, counts = warehouse(store)
    assert counts["raw_testclub__closures_layer"] == 1


class HangingLayer(FakeLayer):
    """A FakeLayer whose first `hangs` page requests time out, as DEC's gisservices.dec.ny.gov pages did."""

    def __init__(self, *args, hangs, **kwargs):
        super().__init__(*args, **kwargs)
        self.hangs = hangs

    def query(self, request, context):
        if "returncountonly" not in {key.lower() for key in request.qs} and self.hangs:
            self.hangs -= 1
            raise requests.exceptions.ReadTimeout("Read timed out. (read timeout=60)")
        return super().query(request, context)


def test_a_monthly_layer_read_waits_out_five_timed_out_pages_and_an_hourly_one_gives_up_after_three_attempts(
    registry, requests_mock, monkeypatch
):
    """refresh-reference.yml runs 37097625268 and 37099504783 each failed the whole monthly lane on one DEC page
    that timed out on all three attempts of lib/http_retry.py's default (5, 30)."""
    pauses = []
    monkeypatch.setattr(http_retry.time, "sleep", pauses.append)
    HangingLayer(requests_mock, LINES_URL, [feature(1), feature(2), feature(3)], hangs=5)
    HangingLayer(requests_mock, CLOSURES_URL, [feature(10)], hangs=5)

    monthly = ArcgisLayer(key="trails", club="testclub", type="trail_lines")
    assert monthly.cadence == "monthly"
    assert len(list(monthly.rows({}))) == 3
    assert pauses == list(MONTHLY_READ_BACKOFF_SECONDS)

    pauses.clear()
    with pytest.raises(requests.exceptions.ReadTimeout):
        list(closures().rows({}))
    assert pauses == list(http_retry.DEFAULT_BACKOFF_SECONDS), "a leg reads a club's resources inside one budget"


def test_an_r2_store_uploads_in_fixed_size_parts_and_a_local_one_passes_no_option(tmp_path):
    """refresh-reference.yml, 37088620131: R2 refused the pin's multipart upload, "All non-trailing parts must have
    the same length"."""

    def kwargs(bucket_url):
        # The factory's own arguments, not its resolved configuration: resolving s3:// credentials with none set
        # sends botocore to the instance metadata address, which the socket guard refuses (pipeline-tests.yml,
        # 37097625630).
        return make_pipeline("monthly", bucket_url, str(tmp_path / "pipelines")).destination.config_params.get("kwargs")

    assert kwargs("s3://our-hike-raw/raw/dlt/monthly") == {"fixed_upload_size": True}
    assert kwargs((tmp_path / "store").as_uri()) is None


def test_a_trail_layer_that_halves_is_refused(registry, store, requests_mock):
    layer = FakeLayer(requests_mock, LINES_URL, [feature(i) for i in range(1, 7)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    lane(store, lines(), closures())

    layer.features, layer.etag = [feature(1), feature(2)], "v2"
    with pytest.raises(ExtractRefused, match="below the 50% floor"):
        lane(store, lines(), closures())
    _, counts = warehouse(store)
    assert counts["raw_testclub__trails"] == 6


# The monthly lane isolates each upstream (_run.ISOLATING_LANES): two monthly layers in two folders,
# so read_each() reads them on two of MONTHLY_READERS' threads.
def monthly_lines():
    return ArcgisLayer(key="trails", club="testclub", type="trail_lines")


def monthly_points():
    return ArcgisLayer(key="closures_layer", club="otherclub", type="points_of_interest")


def month(store, *resources, **options):
    return run_pipeline(
        "monthly", store["bucket_url"], resources=list(resources), pipelines_dir=store["pipelines_dir"], **options
    )


def monthly_counts(store):
    con = duckdb.connect()
    return load_warehouse(con, make_pipeline("monthly", store["bucket_url"], store["pipelines_dir"]))


def test_a_monthly_layer_whose_metadata_is_refused_is_left_out_and_the_other_layers_month_loads(
    registry, store, requests_mock, monkeypatch
):
    """Monthly run 15 (refresh-reference.yml 37208267018) stopped two minutes in: MassGIS's open-space layer
    answered its metadata 403 while dlt was being handed the lane, and nothing else of the month loaded."""
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)
    trails = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2), feature(3)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10), feature(11)])
    first = month(store, monthly_lines(), monthly_points())
    assert first.rows == {"raw_testclub__trails": 3, "raw_otherclub__closures_layer": 2} and not first.isolated

    trails.features, trails.etag = [feature(1), feature(2), feature(3), feature(4)], "v2"
    requests_mock.get(CLOSURES_URL, status_code=403)
    second = month(store, monthly_lines(), monthly_points())

    assert second.outcome == "loaded"
    assert second.rows == {"raw_testclub__trails": 4}
    assert set(second.isolated) == {"raw_otherclub__closures_layer"}
    assert "403" in second.isolated["raw_otherclub__closures_layer"]
    assert _run.exit_status(second) == _run.PARTIAL_EXIT
    assert monthly_counts(store) == {"raw_testclub__trails": 4, "raw_otherclub__closures_layer": 2}


def test_a_monthly_layer_whose_rate_limit_never_lifts_is_left_out_and_keeps_its_last_month(
    registry, store, requests_mock, monkeypatch
):
    """Monthly run 14 (refresh-reference.yml 37207306294) stopped on Oregon Metro's trails, throttled at a page of 1."""
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)
    monkeypatch.setattr("lib.arcgis.time.sleep", lambda seconds: None)
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    points = FakeLayer(requests_mock, CLOSURES_URL, [feature(10), feature(11)])
    month(store, monthly_lines(), monthly_points())

    points.etag = "v2"
    real_query = points.query

    def throttled(request, context):
        if "returncountonly" in {key.lower() for key in request.qs}:
            return real_query(request, context)
        return {"error": {"code": 429, "message": "Unable to perform query. Too many requests.", "details": []}}

    requests_mock.get(CLOSURES_URL + "/query", json=throttled)
    report = month(store, monthly_lines(), monthly_points())

    assert set(report.isolated) == {"raw_otherclub__closures_layer"}
    assert "rate limit" in report.isolated["raw_otherclub__closures_layer"]
    assert monthly_counts(store) == {"raw_testclub__trails": 2, "raw_otherclub__closures_layer": 2}


def test_a_monthly_table_the_run_check_refuses_keeps_its_rows_while_the_others_load(registry, store, requests_mock):
    trails = FakeLayer(requests_mock, LINES_URL, [feature(i) for i in range(1, 7)])
    points = FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    month(store, monthly_lines(), monthly_points())

    trails.features, trails.etag = [feature(1), feature(2)], "v2"
    points.features, points.etag = [feature(10), feature(12)], "v2"
    report = month(store, monthly_lines(), monthly_points())

    assert "below the 50% floor" in report.isolated["raw_testclub__trails"]
    assert report.rows == {"raw_otherclub__closures_layer": 2}
    assert monthly_counts(store) == {"raw_testclub__trails": 6, "raw_otherclub__closures_layer": 2}


def normalize_on_a_worker(monkeypatch, fails=None) -> list[list[str]]:
    """dlt's normalize, its failure carried back as a ProcessPoolExecutor worker's is: pickled, its cause left behind.

    refresh-reference.yml normalizes the monthly lane on --normalize-workers 4
    processes. A worker's exception comes back through
    concurrent.futures.process's _ExceptionWithTraceback: the exception
    pickled, its cause and context dropped, and only its traceback's text
    attached as a _RemoteTraceback. This does exactly that in one process, so
    the case is the same on every Python the suite runs on, without forking
    (pipeline-tests.yml's pytest job on Python 3.14 lost a worker of a real
    pool, run 37214263752; extract/_run.py's MONTHLY_NORMALIZE_WORKERS).

    `fails(files, load_id)`, when given, may raise in the worker in place of
    normalizing; `files` maps each table the worker was handed to its job
    file. Returns the tables each call was handed, one list per call.
    """
    from concurrent.futures.process import _ExceptionWithTraceback

    from dlt.normalize import normalize as dlt_normalize

    real, calls = dlt_normalize.w_normalize_files, []

    def worker(*args, **kwargs):
        files = {ParsedLoadJobFileName.parse(path).table_name: path for path in args[5]}
        calls.append(sorted(files))
        try:
            if fails is not None:
                fails(files, args[4])
            return real(*args, **kwargs)
        except Exception as failure:  # noqa: BLE001 - every worker failure crosses the boundary
            sent = pickle.dumps(_ExceptionWithTraceback(failure, failure.__traceback__))
        raise pickle.loads(sent)

    monkeypatch.setattr(dlt_normalize, "w_normalize_files", worker)
    return calls


def capacity_feature(oid, capacity):
    """feature(), its CAPACITY (hinted bigint from the layer's own esriFieldTypeInteger) set to `capacity`."""
    made = feature(oid)
    return {**made, "properties": {**made["properties"], "CAPACITY": capacity}}


def test_a_monthly_value_that_no_longer_fits_its_columns_type_refuses_that_layer_only_when_a_worker_normalizes_it(
    registry, store, requests_mock, monkeypatch
):
    """dlt's `data_type: freeze` refuses a value retyped under an unchanged hint at normalize, and on the monthly lane's
    worker processes the refusal comes back as NormalizeJobFailed with its cause left behind. contract_breach() found
    it only on one process: on four, the whole month failed with no raw_run and no pin, and every rerun failed the
    same way (the review of the extract layer against dlt 1.30.0, 2026-10-09)."""
    normalize_on_a_worker(monkeypatch)
    trails = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    points = FakeLayer(requests_mock, CLOSURES_URL, [capacity_feature(10, 4)])
    month(store, monthly_lines(), monthly_points())

    trails.features, trails.etag = [feature(1), feature(2), feature(3)], "v2"
    points.features, points.etag = [capacity_feature(10, "four bunks")], "v2"
    report = month(store, monthly_lines(), monthly_points())

    assert set(report.isolated) == {"raw_otherclub__closures_layer"}
    assert "schema contract" in report.isolated["raw_otherclub__closures_layer"]
    assert "data_type" in report.isolated["raw_otherclub__closures_layer"], "dlt's own words, from the worker"
    assert report.rows == {"raw_testclub__trails": 3}
    assert _run.exit_status(report) == _run.PARTIAL_EXIT
    assert monthly_counts(store) == {"raw_testclub__trails": 3, "raw_otherclub__closures_layer": 1}


def test_a_monthly_normalize_a_worker_fails_for_any_other_reason_ends_the_run_red_and_leaves_no_layer_out(
    registry, store, requests_mock, monkeypatch
):
    """A full disk or a bug is not a refusal of one layer, though its NormalizeJobFailed names one layer's job: the run
    stops red as it did, rather than leaving that layer out on a guess, and it does not go round again."""
    trails = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    points = FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    month(store, monthly_lines(), monthly_points())

    def disk_full(files, load_id):
        job = ParsedLoadJobFileName.parse(files["raw_otherclub__closures_layer"]).job_id()
        try:
            raise OSError(errno.ENOSPC, "No space left on device")
        except OSError as error:
            raise NormalizeJobFailed(load_id, job, str(error), []) from error

    calls = normalize_on_a_worker(monkeypatch, disk_full)
    trails.features, trails.etag = [feature(1), feature(2), feature(3)], "v2"
    points.features, points.etag = [feature(10), feature(11)], "v2"
    with pytest.raises(PipelineStepFailed, match="No space left on device") as failed:
        month(store, monthly_lines(), monthly_points())

    assert failed.value.report.isolated == {}
    assert len(calls) == 1, "normalized once: nothing was left out and tried again"
    assert monthly_counts(store) == {"raw_testclub__trails": 2, "raw_otherclub__closures_layer": 1}


def test_a_spooled_monthly_layer_lands_the_rows_its_reader_made(registry, store, requests_mock, tmp_path, monkeypatch):
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    FakeLayer(requests_mock, LINES_URL, [feature(1, "Ridge"), feature(2, "Valley")])
    month(store, monthly_lines())
    con = duckdb.connect()
    load_warehouse(con, make_pipeline("monthly", store["bucket_url"], store["pipelines_dir"]))
    rows = con.execute("select globalid, name, edited, capacity from raw.raw_testclub__trails order by 1").fetchall()
    assert rows == [("g1", "Ridge", 1790000000000, None), ("g2", "Valley", 1790000000000, None)]
    assert not list(temp.glob("read_*")), "the run's spool is removed when it ends"


class CountingResource:
    """A stand-in for read_each(): records how many folders, and how many of its own folder, read at once."""

    def __init__(self, club, name, gauge):
        self.club, self.name, self.table, self.gauge = club, name, f"raw_{club}__{name}", gauge
        self.carries = False

    def column_hints(self):
        return {}

    def rows(self, proofs):
        with self.gauge["lock"]:
            self.gauge["now"] += 1
            self.gauge["folders"][self.club] += 1
            self.gauge["most"] = max(self.gauge["most"], self.gauge["now"])
            self.gauge["most_in_a_folder"] = max(self.gauge["most_in_a_folder"], self.gauge["folders"][self.club])
        time.sleep(0.02)
        with self.gauge["lock"]:
            self.gauge["now"] -= 1
            self.gauge["folders"][self.club] -= 1
        yield {"id": self.name}


def test_read_each_reads_at_most_its_readers_folders_at_once_and_one_resource_of_a_folder_at_a_time(tmp_path):
    gauge = {"lock": threading.Lock(), "now": 0, "most": 0, "most_in_a_folder": 0, "folders": defaultdict(int)}
    to_run = [
        Planned(CountingResource(f"club{club}", f"layer{club}_{layer}", gauge), Freshness.STALE, None, None)
        for club in range(6)
        for layer in range(3)
    ]
    report = _run.RunReport(run_id="r", lane="monthly", outcome="loaded")

    kept, read = _run.read_each(report, to_run, None, spool=tmp_path, readers=2)

    assert len(kept) == 18 and not report.isolated
    assert gauge["most"] == 2 and gauge["most_in_a_folder"] == 1
    assert [list(read[item.resource.name]) for item in to_run[:2]] == [[{"id": "layer0_0"}], [{"id": "layer0_1"}]]
    assert len(list(tmp_path.glob("*.pickle.gz"))) == 18


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


class StatusLayer:
    """A layer read under `status = 'closed'`, offset-paged over the sites closed at the moment each page is asked.

    That is how SQL's OFFSET pages: a site that reopens below the offset
    shifts every later site down one, and one that closes below it shifts
    them up. `edit(pages_served, layer)` runs after each page with features,
    so a test can reopen or close a site part-way through a read.
    """

    def __init__(self, requests_mock, closed, edit=None):
        self.closed = sorted(closed)
        self.edit = edit or (lambda pages_served, layer: None)
        self.pages_served = 0
        requests_mock.get(STATUS_URL, json={"objectIdField": "OBJECTID", "fields": FIELDS})
        requests_mock.get(STATUS_URL + "/query", json=self.query)

    def query(self, request, context):
        params = {key.lower(): value[0] for key, value in request.qs.items()}
        if params.get("returncountonly") == "true":
            return {"count": len(self.closed)}
        offset, size = int(params["resultoffset"]), int(params["resultrecordcount"])
        page = [feature(oid, name=f"Site {oid}") for oid in self.closed[offset : offset + size]]
        if page:
            self.pages_served += 1
            self.edit(self.pages_served, self)
        return {"type": "FeatureCollection", "features": page}


def status_layer():
    return ArcgisLayer(key="status_layer", club="testclub", type="closures")


def test_a_site_that_reopens_between_two_pages_does_not_cost_a_still_closed_site_its_row(registry, requests_mock, monkeypatch):
    """Site 2 reopens after the first page of 3, so the second page starts one site late and site 4 was never served.

    The count after the pages is 6, the rows read are 6, and before the fix
    nothing refused: site 4, still closed, was missing from closures until
    the next read (review finding EXD-1).
    """
    monkeypatch.setattr(arcgis, "PAGE_SIZE", 3)

    def reopen_site_2_after_the_first_page(pages_served, layer):
        if pages_served == 1:
            layer.closed.remove(2)

    StatusLayer(requests_mock, range(1, 8), edit=reopen_site_2_after_the_first_page)
    proofs = {}

    landed = [row["OBJECTID"] for row in status_layer().rows(proofs)]

    assert landed == [1, 3, 4, 5, 6, 7], "read again once the layer moved, so every site closed after the edit lands"
    assert proofs == {"raw_testclub__status_layer": 6}


def test_a_site_that_closes_between_two_pages_is_not_missed_behind_a_repeated_one(registry, requests_mock, monkeypatch):
    """Site 2 closes after the first page, below the offset: the next page repeats site 4 and site 2 is never served.

    Seven rows are read and the server counts seven, so before the fix the
    count check passed with the newly closed site missing.
    """
    monkeypatch.setattr(arcgis, "PAGE_SIZE", 3)

    def close_site_2_after_the_first_page(pages_served, layer):
        if pages_served == 1:
            layer.closed = sorted([*layer.closed, 2])

    StatusLayer(requests_mock, [1, 3, 4, 5, 6, 7], edit=close_site_2_after_the_first_page)

    landed = [row["OBJECTID"] for row in status_layer().rows({})]

    assert sorted(set(landed)) == [1, 2, 3, 4, 5, 6, 7]
    assert len(landed) == 7, "the read that repeated site 4 was not the one that landed"


def test_a_layer_edited_during_both_reads_is_refused_rather_than_landed_short(registry, requests_mock, monkeypatch):
    """A site reopens part-way through the first read and another part-way through the second: neither read is whole."""
    monkeypatch.setattr(arcgis, "PAGE_SIZE", 3)

    def reopen_the_lowest_site_after_each_reads_first_page(pages_served, layer):
        if len(layer.closed) > 3 and pages_served in (1, 3):
            layer.closed.pop(0)

    StatusLayer(requests_mock, range(1, 8), edit=reopen_the_lowest_site_after_each_reads_first_page)

    with pytest.raises(RuntimeError, match="changed while it was read, twice"):
        list(status_layer().rows({}))


def test_a_layer_read_in_one_page_is_not_read_again_when_its_count_moves(registry, requests_mock):
    """One page cannot be shifted by an edit, so a count that moves between the reads before and after it is no reason to read again."""

    def reopen_site_2_after_the_only_page(pages_served, layer):
        if pages_served == 1:
            layer.closed.remove(2)

    layer = StatusLayer(requests_mock, range(1, 4), edit=reopen_site_2_after_the_only_page)

    landed = [row["OBJECTID"] for row in status_layer().rows({})]

    assert landed == [1, 2, 3] and layer.pages_served == 1


def test_a_field_added_to_person_fields_is_dropped_from_a_layer_that_has_not_moved_upstream(
    registry, store, requests_mock, monkeypatch
):
    """The layer answers 304, so only the resource's own definition in its marker can say it must be read again."""
    FakeLayer(requests_mock, LINES_URL, [feature(1, ranger="A. Person")])
    with monkeypatch.context() as before_the_fix:
        before_the_fix.setattr(_kinds, "PERSON_FIELDS", _kinds.PERSON_FIELDS - {"ranger"})
        lane(store, lines())
        con, _ = warehouse(store)
        assert "A. Person" in str(con.execute('select * from raw."raw_testclub__trails"').fetchall()), "the leak"

    second = lane(store, lines())

    assert second.verdicts == {"raw_testclub__trails": "stale"}
    con, _ = warehouse(store)
    assert "A. Person" not in str(con.execute('select * from raw."raw_testclub__trails"').fetchall())
    assert lane(store, lines()).verdicts == {"raw_testclub__trails": "fresh"}, "read again once, then fresh"


def test_definition_digest_moves_with_the_person_fields_and_the_resources_own_fields(registry, monkeypatch):
    digest = _run.definition_digest(lines())
    assert _run.definition_digest(lines()) == digest, "the same definition, built again"
    assert _run.definition_digest(ReviewedFile(key="w", club="c", type="closures", path="w.json", verbatim=True)) != (
        _run.definition_digest(ReviewedFile(key="w", club="c", type="closures", path="w.json"))
    )
    monkeypatch.setattr(_kinds, "PERSON_FIELDS", _kinds.PERSON_FIELDS | {"steward_name"})
    assert _run.definition_digest(lines()) != digest


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


STAFFED_FIELDS = [
    {"name": "OBJECTID", "type": "esriFieldTypeOID"},
    {"name": "NAME", "type": "esriFieldTypeString"},
    {"name": "CreatedBy", "type": "esriFieldTypeString"},
    {"name": "LastEdited", "type": "esriFieldTypeString"},
    {"name": "LAST_EDITOR", "type": "esriFieldTypeString"},
    {"name": "Editor", "type": "esriFieldTypeString"},
    {"name": "TELEPHONE", "type": "esriFieldTypeString"},
    {"name": "created_user", "type": "esriFieldTypeString"},
    {"name": "LastEdBy", "type": "esriFieldTypeString"},
    {"name": "Surveyor", "type": "esriFieldTypeString"},
    {"name": "source", "type": "esriFieldTypeString"},
    {"name": "last_edited_date", "type": "esriFieldTypeDate"},
    {"name": "LastEdit_1", "type": "esriFieldTypeString"},
]
STAFF = {
    "CreatedBy": "a.person",
    "LastEdited": "a.person",
    "LAST_EDITOR": "a.person",
    "Editor": "a.person",
    "TELEPHONE": "555-0100",
    "created_user": "a.person",
    "LastEdBy": "a.person",
    "Surveyor": "a.person",
    "source": "GPS A. Person",
}


class StaffedLayer(FakeLayer):
    """A layer whose staff columns go by every name a club has used, and whose editor tracking names its own creator field."""

    def metadata(self, request, context):
        context.headers["ETag"] = self.etag
        return {
            "objectIdField": "OBJECTID",
            "fields": STAFFED_FIELDS,
            "editFieldsInfo": {"creatorField": "Surveyor", "creationDateField": "last_edited_date"},
        }


def staffed_feature(oid):
    properties = {"OBJECTID": oid, "NAME": "Spring", **STAFF, "last_edited_date": 1790000000000, "LastEdit_1": "2025-02-19"}
    return {"type": "Feature", "properties": properties, "geometry": {"type": "Point", "coordinates": [-74.0, 42.0]}}


def staffed():
    return ArcgisLayer(key="staffed", club="testclub", type="points_of_interest")


def test_no_staff_column_lands_under_any_name_and_the_dates_beside_them_still_do(registry, requests_mock, capsys):
    """The row's `person_fields`, the layer's editFieldsInfo, PERSON_FIELDS and the person-shaped backstop, together.

    `Editor` is in the row's `not_person_fields` and is dropped anyway: that
    list clears the backstop's guesses, never a name PERSON_FIELDS holds. A
    date keeps its column whatever it is called, and `LastEdit_1`, a date
    published as text, loads because its row clears it.
    """
    StaffedLayer(requests_mock, STAFFED_URL, [staffed_feature(1), staffed_feature(2)])
    resource = staffed()

    rows = list(resource.rows({}))
    hints = resource.column_hints()

    landed = {"OBJECTID", "NAME", "last_edited_date", "LastEdit_1", "geometry"}
    assert all(set(row) == landed for row in rows), rows
    assert set(hints) == landed
    asked = {name for r in requests_mock.request_history if "outfields" in r.qs for name in r.qs["outfields"][0].split(",")}
    assert asked and not asked & {name.lower() for name in STAFF}, "never asked for, not only dropped"
    assert "a.person" not in json.dumps(rows) and "555-0100" not in json.dumps(rows)
    printed = capsys.readouterr().out
    assert "['CreatedBy', 'LAST_EDITOR', 'LastEdBy', 'LastEdited', 'TELEPHONE']" in printed, printed


@pytest.mark.parametrize(
    "metadata",
    [
        {"error": {"code": 500, "message": "Service Waypoints/FeatureServer not started"}},
        {"objectIdField": "OBJECTID"},
    ],
    ids=["an error body", "no field list"],
)
def test_a_layer_whose_metadata_names_no_fields_is_refused_before_any_page_is_asked_for_every_field(
    registry, requests_mock, metadata
):
    """With no field list nothing could be left out of the request, so it would have asked outFields=* (review finding EXD-2)."""
    layer = StaffedLayer(requests_mock, STAFFED_URL, [staffed_feature(1)])
    requests_mock.get(STAFFED_URL, json=metadata)

    with pytest.raises(RuntimeError, match="no field list"):
        list(staffed().rows({}))
    asked_pages = [r for r in requests_mock.request_history if "outfields" in r.qs]
    assert asked_pages == [], [r.qs["outfields"] for r in asked_pages]
    assert layer.features, "the layer had a staffed row to give"


def test_a_staff_column_the_metadata_does_not_list_still_never_lands(registry, requests_mock):
    """A row can carry a field its layer document leaves out; the name rules judge it at the row, as they do in the field list."""
    StaffedLayer(requests_mock, STAFFED_URL, [staffed_feature(1)])
    requests_mock.get(
        STAFFED_URL,
        json={
            "objectIdField": "OBJECTID",
            "fields": [field for field in STAFFED_FIELDS if field["name"] in ("OBJECTID", "NAME")],
        },
    )

    rows = list(staffed().rows({}))

    # `last_edited_date` goes too: unlisted, its type is unknown, so it is judged by its editor-shaped name.
    # So does `Surveyor`, which the person-shaped backstop reads as a person's field.
    assert set(rows[0]) == {"OBJECTID", "NAME", "LastEdit_1", "geometry"}, rows[0]
    assert "GPS A. Person" not in json.dumps(rows), "the row's person_fields, `source`, is judged by name too"
    assert "555-0100" not in json.dumps(rows)


@pytest.mark.parametrize("name", ["MANAGER", "Park_Manager", "SUPERINTENDENT", "STEWARD", "SURVEYOR", "CREATEUSER", "EDITUSER"])
def test_a_manager_steward_or_surveyor_column_and_an_all_capitals_user_column_are_person_shaped(registry, name):
    """Names the backstop missed, so such a field loaded unless a person had named it on its row (review finding EXD-3).

    PA DCNR's park layer loaded a `MANAGER` whose values have the shape of
    people's names; NPS's layers spell editor tracking `CREATEUSER` and
    `EDITUSER`, one word each.
    """
    layer = ArcgisLayer(key="trails", club="testclub", type="trail_lines")

    dropped = layer.dropped_fields({"fields": [{"name": name, "type": "esriFieldTypeString"}]})

    assert dropped == {name.lower(): "a person-shaped name"}


def test_a_manager_column_a_row_clears_as_an_agency_still_loads(registry):
    """`not_person_fields` clears the new words as it clears `owner`: Mohonk's `Manager` is "Mohonk Preserve" on every row."""
    entries = json.loads(registry.read_text())
    next(e for e in entries["sources"] if e["key"] == "trails")["not_person_fields"] = ["Manager"]
    registry.write_text(json.dumps(entries))
    _kinds._registry.cache_clear()
    layer = ArcgisLayer(key="trails", club="testclub", type="trail_lines")

    assert layer.dropped_fields({"fields": [{"name": "Manager", "type": "esriFieldTypeString"}]}) == {}


@pytest.mark.parametrize(
    ("key", "field", "dropped"),
    [
        ("pasda_state_park_amenities", "MANAGER", True),
        ("mohonk_trails", "Manager", False),
        ("cotrex_trailheads", "manager", False),
        ("pcta_trailheads", "external_trailheadManager", False),
        ("ridgetrail_campsites", "MANAGER", False),
    ],
)
def test_each_registered_layers_manager_column_is_ruled_on_its_own_row(key, field, dropped):
    """The real rows: PA DCNR's park managers never load; the four whose row records the column as agencies keep it."""
    layer = ArcgisLayer(key=key, club="testclub", type="points_of_interest")

    verdict = layer.dropped_fields({"fields": [{"name": field, "type": "esriFieldTypeString"}]})

    assert bool(verdict) is dropped, verdict


def test_a_name_added_to_a_rows_person_fields_reads_an_unmoved_layer_again(registry, monkeypatch):
    """The row's lists live in sources.json, not in the resource, so definition_digest() has to read them itself."""
    before = _run.definition_digest(staffed())
    entries = json.loads(registry.read_text())
    next(e for e in entries["sources"] if e["key"] == "staffed")["person_fields"].append("Maint_Name")
    registry.write_text(json.dumps(entries))
    _kinds._registry.cache_clear()

    after_the_row = _run.definition_digest(staffed())
    assert after_the_row != before
    monkeypatch.setattr(_kinds, "PERSON_SHAPED", _kinds.re.compile("steward"))
    assert _run.definition_digest(staffed()) != after_the_row, "a change to the backstop reads every layer again too"


def z_centerline():
    return ArcgisLayer(key="centerline_z", club="testclub", type="elevation", cadence_override="hourly", cadence_reason="a test")


def test_a_layer_registered_with_return_z_lands_each_vertex_elevation_through_to_a_geometry(registry, store, requests_mock):
    """f=geojson drops Z, so a row with `return_z: true` is read as Esri JSON and lands GeoJSON whose vertices keep it."""
    FakeZLayer(requests_mock, LINES_Z_URL, [z_feature(1, 1600.48), z_feature(2, 1149.9), z_feature(3, 443.03)])

    report = lane(store, z_centerline())

    assert report.outcome == "loaded"
    assert report.rows == {"raw_testclub__centerline_z": 3}
    pages = [r.qs for r in requests_mock.request_history if r.path.endswith("/query") and "resultoffset" in r.qs]
    assert pages and all(qs["f"] == ["json"] and qs["returnz"] == ["true"] for qs in pages)
    con, _ = warehouse(store)
    con.execute("INSTALL spatial; LOAD spatial;")
    starts = con.execute(
        "select objectid, st_z(st_startpoint(st_geomfromgeojson(geometry::varchar))),"
        " st_z(st_endpoint(st_geomfromgeojson(geometry::varchar)))"
        " from raw.raw_testclub__centerline_z order by objectid"
    ).fetchall()
    assert starts == [(1, 1600.48, 1590.98), (2, 1149.9, 1140.4), (3, 443.03, 433.53)]


def test_a_layer_without_return_z_is_asked_for_exactly_what_it_was_asked_for_before(registry, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])

    rows = list(lines().rows({}))

    assert rows[0]["geometry"] == {"type": "Point", "coordinates": [-74.0, 42.0]}
    pages = [r.qs for r in requests_mock.request_history if r.path.endswith("/query") and "resultoffset" in r.qs]
    assert pages and all(set(qs) == {"where", "outfields", "outsr", "f", "resultoffset", "resultrecordcount"} for qs in pages)
    assert all(qs["f"] == ["geojson"] for qs in pages)


def test_a_layer_whose_server_refuses_pagination_is_read_whole_by_object_id(registry, requests_mock):
    """cicgis.org's CAJO layer's shape (measured 2026-10-03): supportsPagination false, and a paged query an error."""
    ids = list(range(5))

    def metadata(request, context):
        fields = [{"name": "FID", "type": "esriFieldTypeOID"}, {"name": "NAME", "type": "esriFieldTypeString"}]
        return {"fields": fields, "maxRecordCount": 2, "advancedQueryCapabilities": {"supportsPagination": False}}

    def query(request, context):
        asked = {key.lower(): value[0] for key, value in parse_qs(request.text or "").items()}
        asked.update({key.lower(): value[0] for key, value in request.qs.items()})
        if "resultoffset" in asked:
            return {"error": {"code": 400, "message": "Pagination is not supported.", "details": []}}
        if asked.get("returncountonly") == "true":
            return {"count": len(ids)}
        if asked.get("returnidsonly") == "true":
            return {"objectIdFieldName": "FID", "objectIds": ids}
        wanted = [int(oid) for oid in asked["objectids"].split(",")]
        assert len(wanted) <= 2, "a batch is never larger than the layer's own maxRecordCount"
        point = {"type": "Point", "coordinates": [-76.0, 38.0]}
        return {
            "features": [
                {"type": "Feature", "id": oid, "properties": {"FID": oid, "NAME": "CAJO"}, "geometry": point} for oid in wanted
            ]
        }

    requests_mock.get(UNPAGED_URL, json=metadata)
    requests_mock.get(UNPAGED_URL + "/query", json=query)
    requests_mock.post(UNPAGED_URL + "/query", json=query)
    resource = ArcgisLayer(key="unpaged", club="testclub", type="trail_lines")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert [row["FID"] for row in rows] == ids
    assert proofs == {resource.table: 5}, "the proof is still the server's returnCountOnly"


def test_turning_return_z_on_reads_a_layer_again_and_leaves_every_other_digest_as_it_was(registry):
    def digest_before_return_z(resource):
        definition = {
            "resource": repr(resource),
            "person_fields": sorted(_kinds.PERSON_FIELDS),
            "person_shaped": _kinds.PERSON_SHAPED.pattern,
            "field_rules": getattr(resource, "field_rules", None),
            "wordpress_dropped": sorted(_kinds.WP_DROPPED),
            "withheld_columns": sorted(_kinds.WITHHELD_COLUMNS),
            "where": getattr(resource, "where", None),
        }
        return hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()

    assert _run.definition_digest(lines()) == digest_before_return_z(lines()), "a marker recorded before return_z still matches"
    assert _run.definition_digest(z_centerline()) != digest_before_return_z(z_centerline())


#: Two `editFieldsInfo` answers for onprem_dated, whose freshness.field is UPDATED: editor tracking keeping another
#: date, and keeping UPDATED. An unchanged on-prem fingerprint is FRESH only beside the second (_onprem_check()).
ANOTHER_DATE = {"editDateField": "LAST_EDITED_DATE", "editorField": "LAST_EDITED_USER"}
ITS_OWN_DATE = {"editDateField": "updated", "editorField": "editor"}


def test_an_onprem_layer_with_no_maintained_date_is_always_read(registry, requests_mock):
    resource = ArcgisLayer(key="onprem_undated", club="testclub", type="trail_lines")
    assert resource.platform == "onprem"
    assert resource.change_check({"n": "1", "max_oid": "1", "max_date": "1"}) == (Freshness.UNKNOWN, None)


def test_an_onprem_fingerprint_sees_a_delete_that_the_edit_date_alone_would_miss(registry, requests_mock):
    requests_mock.get(ONPREM_URL, json={"objectIdField": "OBJECTID", "editFieldsInfo": ITS_OWN_DATE})
    answer = {"features": [{"attributes": {"n": 315, "max_oid": 900, "max_date": 1790000000000}}]}
    requests_mock.get(ONPREM_URL + "/query", json=answer)
    resource = ArcgisLayer(key="onprem_dated", club="testclub", type="points_of_interest")

    verdict, marker = resource.change_check(None)
    assert verdict is Freshness.STALE
    assert resource.change_check(marker) == (Freshness.FRESH, marker)

    answer["features"][0]["attributes"]["n"] = 314  # a lean-to deleted: the newest edit date does not move
    assert resource.change_check(marker)[0] is Freshness.STALE


def test_an_onprem_fingerprint_sees_a_redrawn_line_that_count_ids_and_the_date_all_miss(registry, requests_mock):
    """A line moved in place under an unchanged edit date: only the summed length moves (the dlt skill's rule 4).

    Even editor tracking's own date can stay put: tracking can be switched off for a bulk edit (Reasoned; not seen on
    a registered layer)."""
    fields = [
        {"name": "OBJECTID", "type": "esriFieldTypeOID"},
        {"name": "UPDATED", "type": "esriFieldTypeDate"},
        {"name": "Shape_Length", "type": "esriFieldTypeDouble"},
    ]
    requests_mock.get(ONPREM_URL, json={"objectIdField": "OBJECTID", "fields": fields, "editFieldsInfo": ITS_OWN_DATE})
    asked = []
    answer = {"features": [{"attributes": {"n": 40, "max_oid": 40, "max_date": 1790000000000, "sum_measure": 81234.5}}]}

    def statistics(request, context):
        outstatistics = json.loads(parse_qs(urlsplit(request.url).query)["outStatistics"][0])
        asked.append({(stat["statisticType"], stat["onStatisticField"]) for stat in outstatistics})
        return answer

    requests_mock.get(ONPREM_URL + "/query", json=statistics)
    resource = ArcgisLayer(key="onprem_dated", club="testclub", type="trail_lines")

    verdict, marker = resource.change_check(None)
    assert verdict is Freshness.STALE
    assert ("sum", "Shape_Length") in asked[0]
    assert resource.change_check(marker) == (Freshness.FRESH, marker)

    answer["features"][0]["attributes"]["sum_measure"] = 81240.25  # a reroute: same rows, same ids, same date
    assert resource.change_check(marker)[0] is Freshness.STALE


@pytest.mark.parametrize(
    ("type_", "edit_fields", "unchanged"),
    [
        ("warnings", None, Freshness.UNKNOWN),
        ("warnings", ANOTHER_DATE, Freshness.UNKNOWN),
        ("warnings", ITS_OWN_DATE, Freshness.FRESH),
        ("points_of_interest", None, Freshness.UNKNOWN),
        ("points_of_interest", ANOTHER_DATE, Freshness.UNKNOWN),
        ("points_of_interest", ITS_OWN_DATE, Freshness.FRESH),
    ],
    ids=[
        "hourly, the server names no edit tracking",
        "hourly, edit tracking keeps another date",
        "hourly, the date is edit tracking's own",
        "monthly, the server names no edit tracking",
        "monthly, edit tracking keeps another date",
        "monthly, the date is edit tracking's own",
    ],
)
def test_an_unchanged_onprem_fingerprint_is_fresh_only_beside_edit_trackings_own_date_on_any_cadence(
    registry, requests_mock, type_, edit_fields, unchanged
):
    """A burn restriction or a lean-to's capacity edited in place moves no count, id or length, and moves a maintained
    date only when its publisher moves it; the server promises that only of the date its editor tracking keeps
    (`editFieldsInfo.editDateField`). An unchanged fingerprint is FRESH for as long as it stays unchanged, so on the
    monthly lane such an edit could go unseen indefinitely. Read 2026-10-09: five of the eight hourly on-prem layers
    with a maintained date, and all 17 monthly ones, name a date their servers do not (the dlt skill's rule 4)."""
    metadata = {"objectIdField": "OBJECTID", "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}]}
    requests_mock.get(ONPREM_URL, json={**metadata, "editFieldsInfo": edit_fields} if edit_fields else metadata)
    answer = {"features": [{"attributes": {"n": 83, "max_oid": 83, "max_date": 1791496200000}}]}
    requests_mock.get(ONPREM_URL + "/query", json=answer)
    resource = ArcgisLayer(key="onprem_dated", club="testclub", type=type_)

    verdict, marker = resource.change_check(None)
    assert verdict is Freshness.STALE

    assert resource.change_check(marker) == (unchanged, marker)
    answer["features"][0]["attributes"]["n"] = 82
    assert resource.change_check(marker)[0] is Freshness.STALE, "a fingerprint that moved still reads as moved"


def test_an_onprem_point_layer_fingerprints_without_a_measure(registry, requests_mock):
    """A point layer has no length or area field, so its statistics stay the three they were."""
    requests_mock.get(
        ONPREM_URL, json={"objectIdField": "OBJECTID", "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}]}
    )
    asked = []

    def statistics(request, context):
        outstatistics = json.loads(parse_qs(urlsplit(request.url).query)["outStatistics"][0])
        asked.append({stat["outStatisticFieldName"] for stat in outstatistics})
        return {"features": [{"attributes": {"n": 5, "max_oid": 5, "max_date": 1790000000000}}]}

    requests_mock.get(ONPREM_URL + "/query", json=statistics)
    verdict, marker = ArcgisLayer(key="onprem_dated", club="testclub", type="points_of_interest").change_check(None)
    assert verdict is Freshness.STALE
    assert asked == [{"n", "max_oid", "max_date"}]
    assert set(marker) == {"n", "max_oid", "max_date"}


def test_an_onprem_fingerprint_asks_for_the_layers_own_id_field_when_its_metadata_does_not_name_one(registry, requests_mock):
    """CAJO's shape (measured 2026-10-03): no objectIdField key, and its id field is FID, typed esriFieldTypeOID."""
    fields = [{"name": "FID", "type": "esriFieldTypeOID"}, {"name": "UPDATED", "type": "esriFieldTypeDate"}]
    requests_mock.get(ONPREM_URL, json={"fields": fields})

    def statistics(request, context):
        # Read off the URL itself: requests_mock's `qs` lowercases values, and the JSON's keys with them.
        outstatistics = json.loads(parse_qs(urlsplit(request.url).query)["outStatistics"][0])
        if {stat["onStatisticField"] for stat in outstatistics} != {"FID", "UPDATED"}:
            return {"error": {"code": 400, "message": "Unable to complete operation."}}
        return {"features": [{"attributes": {"n": 843, "max_oid": 842, "max_date": 1790000000000}}]}

    requests_mock.get(ONPREM_URL + "/query", json=statistics)
    resource = ArcgisLayer(key="onprem_dated", club="testclub", type="trail_lines")

    verdict, marker = resource.change_check(None)

    assert verdict is Freshness.STALE and marker == {"n": "843", "max_oid": "842", "max_date": "1790000000000"}
    # Unchanged, so not STALE; and read anyway, since CAJO's metadata names no editor-tracking date.
    assert resource.change_check(marker) == (Freshness.UNKNOWN, marker)


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"objectIdField": "OBJECTID_1", "fields": [{"name": "FID", "type": "esriFieldTypeOID"}]}, "OBJECTID_1"),
        ({"fields": [{"name": "NAME", "type": "esriFieldTypeString"}, {"name": "FID", "type": "esriFieldTypeOID"}]}, "FID"),
        ({"fields": [{"name": "NAME", "type": "esriFieldTypeString"}]}, "OBJECTID"),
        ({}, "OBJECTID"),
    ],
)
def test_the_object_id_field_is_the_metadatas_then_the_oid_typed_field_then_objectid(metadata, expected):
    assert _kinds.object_id_field(metadata) == expected


def test_a_change_check_that_errors_is_unknown_and_fetches(registry, requests_mock):
    requests_mock.get(LINES_URL, status_code=503)
    assert lines().change_check({"etag": "v1"}) == (Freshness.UNKNOWN, None)


def test_run_check_wants_one_org_row_per_club(registry):
    resource = catalogue_row()
    planned = [
        Planned(resource.__class__(key=resource.key, club=club, type="org"), Freshness.STALE, None, None) for club in ("a", "b")
    ]
    assert run_check(planned, {"raw_extract__orgs": 1}, {}, {}) == [
        "raw_extract__orgs: 1 rows for 2 managing clubs; each club's catalogue row is exactly one"
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
        # nysdec/warnings.py's two, decision 53 phase B (2026-10-03); decision 63 (2026-10-04) ships the HAB
        # reports and holds the big-game seasons until their season text is parsed.
        "nysdec_hab_reports",
        "nysdec_big_game_seasons",
        # nysdec/closures.py's backcountry page, decision 53 phase B and decision 55 (2026-10-03): registered, not shipped.
        "nysdec_adk_backcountry",
        # Decision 54's places layers (nysdec/places.py, registered 2026-10-03).
        "dec_lands",
        "dec_conservation_easements",
        "dec_wildlife_management_areas",
        "dec_adirondack_park_boundary",
        "dec_catskill_park_boundary",
        # nysdec/podcasts.py's feed, decision 54 wave 3, section C (registered 2026-10-04, not shipped).
        "dec_does_what_podcast",
    }
    assert claims["dec_does_what_podcast"]["type"] == "podcasts"
    assert claims["dec_does_what_podcast"]["reaches_hikers"] is False
    assert claims["dec_lands"]["type"] == "places"
    # Flipped 2026-10-04 under decision 63, once int_places__club_units read the places union; DEC's
    # conservation easements stay held (no place_kind filter is built for them).
    assert claims["dec_lands"]["reaches_hikers"] is True
    assert claims["dec_conservation_easements"]["reaches_hikers"] is False
    assert claims["nysdec_hab_reports"]["type"] == "warnings"
    assert claims["nysdec_hab_reports"]["reaches_hikers"] is True
    assert claims["nysdec_big_game_seasons"]["reaches_hikers"] is False


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


def test_a_podcast_feed_never_lands_a_tag_that_names_a_person(registry, requests_mock):
    """PodcastFeed, which atc/podcasts.py reads The Green Tunnel with, leaves out every tag in PERSON_TAGS, as its
    subclass PodcastEpisodes does: RSS's <author> is an e-mail address, and itunes:owner carries one."""
    item = (
        "<item><guid>g-1</guid><title>One</title><author>someone@example.org (Some One)</author>"
        "<itunes:author>Some One</itunes:author><itunes:owner><itunes:email>owner@example.org</itunes:email>"
        "</itunes:owner><dc:creator>Some One</dc:creator><itunes:duration>12:00</itunes:duration></item>"
    )
    feed_xml = (
        '<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<channel><title>A Trail Show</title><link>https://example.org</link>{item}</channel></rss>"
    ).encode()
    requests_mock.get(FEED_URL, content=feed_xml, headers={"ETag": 'W/"v1"'})
    [row] = list(PodcastFeed(key="a_podcast", club="testclub", type="podcasts").rows({}))
    assert row["itunes_duration"] == "12:00"
    assert not {"author", "itunes_author", "itunes_owner", "ns_creator"} & set(row), row
    assert "example.org" not in "".join(str(value) for value in row.values() if value != "https://example.org")


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

    def __init__(self, requests_mock, rows, *, updated="2026-09-16T20:43:14.951Z", count=None, geometry=True):
        self.rows, self.updated, self.count, self.geometry = rows, updated, count, geometry
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
                "geometry": {"type": "Point", "coordinates": [-73.9, 40.7]} if self.geometry else None,
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


def test_a_socrata_first_load_whose_every_geometry_is_null_still_lands_its_geometry_column(registry, store, requests_mock):
    """The dlt skill's rule 1. dlt creates no column it never saw a value for, so with no hint a first load of rows
    whose geometry is null on every one landed no `geometry` column, and the base model reading it would fail."""
    FakeSocrata(requests_mock, [1, 2], geometry=False)

    month(store, greenways())

    with duckdb.connect() as con:
        load_warehouse(con, make_pipeline("monthly", store["bucket_url"], store["pipelines_dir"]))
        columns = dict(
            con.execute(
                "select column_name, data_type from information_schema.columns where table_name = 'raw_testclub__greenways'"
            ).fetchall()
        )
    assert "geometry" in columns, sorted(columns)
    assert columns["_socrata_id"] == "VARCHAR"


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


def test_a_socrata_dataset_keeps_a_gap_between_its_requests_to_a_host_that_asks_for_one(registry, requests_mock, gate_clock):
    """NYC's portal asks `Crawl-delay: 1`, and its check, pages and count went back to back (review finding EXD-4).

    The row's `crawl_delay` is 1, under DEFAULT_HOST_GAP_SECONDS, so the gap kept is the 2 s floor every reader keeps.
    """
    FakeSocrata(requests_mock, [1, 2, 3])

    greenways().change_check(None)
    list(greenways().rows({}))

    assert len(requests_mock.request_history) == 4, "the check, a page, the empty page after it, the count"
    assert gate_clock == [_notices.DEFAULT_HOST_GAP_SECONDS] * 3


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


def add_to_rows_person_fields(registry, key: str, name: str) -> None:
    """A privacy fix made where it is made: one more name in the sources.json row's `person_fields`."""
    entries = json.loads(registry.read_text())
    next(entry for entry in entries["sources"] if entry["key"] == key).setdefault("person_fields", []).append(name)
    registry.write_text(json.dumps(entries))
    _kinds._registry.cache_clear()


def test_a_name_added_to_a_wordpress_rows_person_fields_is_dropped_on_the_next_run_of_a_site_that_has_not_moved(
    registry, store, requests_mock
):
    """WordpressPosts once read the row's `person_fields` outside `field_rules`, so the digest in its marker used to
    stay put, the unmoved site answered FRESH, and the column the row now leaves out kept serving until the club
    next edited a post."""
    post = wp_post(1)
    post["content"] = {"rendered": "<p>Call the maintainer at 555-0100 or maint@example.org</p>"}
    FakeWordpress(requests_mock, [post])
    lane(store, alerts())
    con, _ = warehouse(store)
    assert "555-0100" in str(con.execute('select * from raw."raw_testclub__alerts"').fetchall()), "the leak"

    add_to_rows_person_fields(registry, "alerts", "content")
    second = lane(store, alerts())

    assert second.verdicts == {"raw_testclub__alerts": "stale"}, "the site has not moved; the row has"
    con, _ = warehouse(store)
    assert "555-0100" not in str(con.execute('select * from raw."raw_testclub__alerts"').fetchall())
    assert lane(store, alerts()).verdicts == {"raw_testclub__alerts": "fresh"}, "read again once, then fresh"


def test_a_name_added_to_a_podcast_rows_person_fields_moves_its_definition_digest(registry):
    """A podcast feed's conditional GET answers FRESH while the feed is unchanged, so only the digest can see it."""
    from extract._content import PodcastEpisodes

    def episodes():
        return PodcastEpisodes(key="a_podcast", club="testclub", type="podcasts")

    before = _run.definition_digest(episodes())

    add_to_rows_person_fields(registry, "a_podcast", "description")

    assert "description" in episodes().field_rules["person_fields"]
    assert _run.definition_digest(episodes()) != before


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


def test_the_hike_finder_waits_its_hosts_crawl_delay_after_the_sign_in_and_only_that_long_between_pages(
    registry, requests_mock, monkeypatch, gate_clock
):
    """The host asks `Crawl-delay: 10`; the sign-in's POST kept only fetch_hikefinder's 0.5 s (review finding EXD-4).

    Every request now passes the host's gate, the POST included, and the gate
    is the only wait: 10 s end to start, never the gate's 10 and a throttle's
    10 one after the other.
    """
    retry_sleeps = []
    monkeypatch.setattr(http_retry.time, "sleep", retry_sleeps.append)
    monkeypatch.setenv("HIKEFINDER_PASSWORD", "fixture-not-a-password")
    requests_mock.post(HIKES + "hikes.php", text="signed in")
    requests_mock.get(HIKES + "hikes.php", text='Results (1 hikes found) <a href="hike.php?id=1">a</a>')
    requests_mock.get(HIKES + "hike.php?id=1", text=page(gpx=True))
    requests_mock.get(HIKES + "download_gpx.php?id=1", text=GPX)

    rows = list(PublishedHikes(key="hikes", club="testclub", type="suggested_hikes").rows({}))

    assert len(rows) == 1 and rows[0]["gpx"] == GPX
    assert [r.method for r in requests_mock.request_history] == ["POST", "GET", "GET", "GET"]
    assert gate_clock == [10, 10, 10], "the listing, the hike and its track each wait 10 s after the request before"
    assert all(seconds < 1 for seconds in retry_sleeps), retry_sleeps


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
    # An invented title and date, so this holds the manifest; the read itself is the test below.
    monkeypatch.setattr(
        _kinds,
        "club_pdf_document_info",
        lambda body: {"title": "Fixture Water Update May 2011.xlsx", "created": "2026-03-02T15:00:00-05:00"},
    )
    requests_mock.get(
        PDF_URL, content=b"%PDF-1.7 water", headers={"ETag": '"w1"', "Last-Modified": "Mon, 02 Mar 2026 00:00:00 GMT"}
    )
    rows = list(water().rows({}))
    assert [row["mile"] for row in rows] == [0.8, 7.3, 0.2, 2.8, 38.0, 80.7]
    assert rows[0]["_document"]["etag"] == '"w1"' and rows[0]["_document"]["bytes"] == 14
    assert rows[0]["_document"]["last_modified"] == "Mon, 02 Mar 2026 00:00:00 GMT", "the club's own date is in the warehouse"
    # The HTTP date is the file's; the title is what says how old the data in it is (decision 75).
    assert rows[0]["_document"]["title"] == "Fixture Water Update May 2011.xlsx"
    assert rows[0]["_document"]["created"] == "2026-03-02T15:00:00-05:00"


def test_a_club_pdfs_own_title_and_creation_date_are_read_through_pypdf_and_a_pdf_stating_neither_reads_as_none():
    """club_pdf_document_info on PDFs written here with pypdf, which the pipeline suite now installs (WF4 of the PR
    #1805 review). The first is GATC's case with an invented title: a title naming an older year than the file's
    HTTP date (decision 75). Unreadable bytes are None for both, never a failed load."""
    from io import BytesIO

    import pypdf

    def pdf(metadata: dict) -> bytes:
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_metadata(metadata)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    dated = pdf({"/Title": "Fixture Water Update July 2020.xlsx", "/CreationDate": "D:20200715120000-04'00'"})
    assert _kinds.club_pdf_document_info(dated) == {
        "title": "Fixture Water Update July 2020.xlsx",
        "created": "2020-07-15T12:00:00-04:00",
    }
    assert _kinds.club_pdf_document_info(pdf({})) == {"title": None, "created": None}
    assert _kinds.club_pdf_document_info(pdf({"/Title": "  ", "/CreationDate": "not a date"})) == {"title": None, "created": None}
    assert _kinds.club_pdf_document_info(b"%PDF-1.7 not a document") == {"title": None, "created": None}


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
    same_bytes = {"sha256": marker["sha256"], "manifest": _kinds.CLUB_PDF_MANIFEST}
    assert water().change_check(same_bytes)[0] is Freshness.FRESH, "WordPress re-served the same bytes"
    document["bytes"] = b"%PDF-1.7 water, revised"
    assert water().change_check(same_bytes)[0] is Freshness.STALE


def test_a_club_pdf_waits_its_hosts_crawl_delay_behind_the_other_reader_on_that_host(registry, requests_mock, gate_clock):
    """GATC's host asks `Crawl-delay: 10`, and its peaks page and water PDF are read one after the other.

    The page reader passes the host's gate; the PDF did not, so it was asked
    straight after the page and the page after it waited only its own 10 s
    from the first (review finding EXD-4).
    """
    page = "https://club.example.org/for-hikers/peaks/"
    requests_mock.get(page, text="<html>peaks</html>")
    requests_mock.get(PDF_URL, content=b"%PDF-1.7 water", headers={"ETag": '"w1"'})
    page_reader = _notices.polite(_kinds.session(), 10.0)

    page_reader.get(page)
    water().change_check(None)
    page_reader.get(page)

    assert [r.url for r in requests_mock.request_history] == [page, PDF_URL, page]
    assert gate_clock == [10.0, 10.0], "the PDF waits 10 s after the page, and the page 10 s after the PDF"


def test_a_club_pdf_that_now_redirects_to_another_host_is_unknown_and_never_read_as_the_clubs(registry, requests_mock):
    """A moved upload served from a host nobody read robots.txt or terms for is not the club's PDF (review finding EXD-10)."""
    elsewhere = "https://parked-domain.example.net/water.pdf"
    requests_mock.get(PDF_URL, status_code=301, headers={"Location": elsewhere})
    requests_mock.get(elsewhere, content=b"%PDF-1.7 not the club's", headers={"ETag": '"p1"'})

    assert water().change_check(None) == (Freshness.UNKNOWN, None)
    with pytest.raises(RuntimeError, match="another host"):
        list(water().rows({}))


def test_a_club_pdf_loaded_under_an_older_manifest_is_read_again_whatever_its_bytes(registry, requests_mock):
    """Rows loaded before `_document` carried the PDF's own title lack it, and unchanged bytes would keep them for
    good, so a marker without the current manifest version is STALE, asked for without validators so a 304 cannot
    keep it either."""

    def answer(request, context):
        if request.headers.get("If-None-Match") == '"w1"':
            context.status_code = 304
            return b""
        context.headers["ETag"] = '"w1"'
        return b"%PDF-1.7 water"

    requests_mock.get(PDF_URL, content=answer)
    _, marker = water().change_check(None)
    old = {key: value for key, value in marker.items() if key != "manifest"}
    verdict, renewed = water().change_check(old)
    assert verdict is Freshness.STALE and renewed["manifest"] == _kinds.CLUB_PDF_MANIFEST
    assert "If-None-Match" not in requests_mock.request_history[-1].headers, "no validator, so no 304 can keep it"
    assert water().change_check(renewed) == (Freshness.FRESH, renewed), "once read again, a 304 is FRESH"


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
    return BucketListing(key="tnm_3dep_13_current", club="usgs", type="elevation")


def test_a_bucket_listing_walks_every_page_of_its_fetchers_prefix_and_lands_no_object(requests_mock):
    keys = [f"{DEM_PREFIX}n4{i}w074/USGS_13_n4{i}w074.{ext}" for i in range(3) for ext in ("tif", "xml")]
    bucket = FakeBucket(requests_mock, keys)
    proofs = {}
    rows = list(dem_listing().rows(proofs))
    assert dem_listing().table == "raw_usgs__tnm_3dep_13_current"
    assert [row["key"] for row in rows] == sorted(keys), "every object, the .xml beside each tile included"
    assert proofs["raw_usgs__tnm_3dep_13_current"] == 6
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
