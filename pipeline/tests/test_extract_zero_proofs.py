"""The allowed zero, reader kind by reader kind: a table lands zero rows only beside the upstream's own count of zero.

pipeline/ELT.md, "The data checks" and "A full reload that cannot empty a
safety table", and the dlt skill's rule 2: a closures or warnings table (or a
row whose sources.json `may_be_empty` allows it) may land zero rows only when
the upstream's own count, read in the same run, says zero. Without that count
the zero is UNKNOWN and the run check refuses it, because an empty answer from
a failed fetch looks exactly like a quiet trail.

Which count is the upstream's own is a property of the reader kind, declared
on each kind as Resource.zero_proof (extract/_contract.py) and pinned here in
READS_UPSTREAM_COUNT. Three things are held:

1. Every reader kind states its answer on its own class, and the table below
   names every kind, so a new reader is refused until somebody decides.
2. For every kind, as extract/_run.py's run_check() reads it: a zero with no
   count fails; a zero beside a count of 0 passes only where the kind reads
   the upstream's own count, since a count a reader makes of what it parsed
   proves nothing; and a may-be-empty table of a kind that reads no such count
   keeps the 50% shrink floor every other table has.
3. For each kind whose own read of a zero had no test of its own, the read
   itself, against a mocked upstream: the upstream saying zero records a proof
   of 0 and the run check passes it, and an answer with no count records none
   (or raises) and the run check refuses it. The kinds tested elsewhere are
   named in READS_UPSTREAM_COUNT's comments.

Every server is requests_mock under conftest.py's socket guard; every body is
invented in the shape its upstream answers.
"""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil

import fsspec
import pytest

import extract
import fetch_club_pdfs
from extract import _geofabrik, _json_apis, _kinds, _notices, _pages_points, _pdf_points
from extract._contract import Resource
from extract._geofabrik import CURRENT_PREFIX, INDEX_NAME, GeofabrikExtracts, bind_store, unbind_store
from extract._gis_files import GisFile
from extract._json_apis import MediawikiAnnouncements, UsgsElevatedVolcanoes
from extract._kinds import ORGS_TABLE, SocrataDataset, WordpressPosts
from extract._ogc import JsonFeatures, OgcFeatures
from extract._pages_points import PagePoints
from extract._pdf_points import PdfPoints
from extract._run import COLLAPSE_FLOOR, Planned, run_check
from lib import geofabrik, http_retry
from lib.freshness_state import Freshness
from tests.test_extract_json_apis import VOLCANOES, WIKI, FakeWiki
from tests.test_extract_run import GREENWAY_WHERE, SOCRATA, WP, FakeSocrata, FakeWordpress

#: Every reader kind, by class name, and whether the count it records is the upstream's own (its zero_proof is not
#: None). True is what lets its table land zero rows where its type or its row allows one. Where the kind's own zero
#: is tested elsewhere, the comment names the test.
READS_UPSTREAM_COUNT = {
    # test_extract_run.py: test_every_closure_lifted_loads_as_an_empty_table_beside_the_servers_own_zero and
    # test_an_empty_answer_with_no_count_is_refused_and_the_last_good_closures_stay.
    "ArcgisLayer": True,
    # test_extract_atc_trail_update_pages.py: test_an_empty_sitemap_refuses_the_read_rather_than_proving_a_zero.
    "AtcTrailUpdatePages": True,
    "BucketListing": True,
    "CatalogueRow": False,  # held to exactly one row per club instead (test_extract_run.py)
    "ClubPdf": False,
    # test_extract_conditions.py: test_a_week_with_no_dispute_lands_an_empty_table_with_the_querys_own_computed_columns.
    "ConditionsQuery": True,
    "ContentPages": False,
    "ContentPdf": False,
    # test_extract_json_apis.py: test_every_park_answering_an_empty_list_is_a_proven_zero.
    "DcnrParkAdvisories": True,
    # test_extract_notices.py: test_an_empty_feed_proves_its_own_zero_and_a_closures_leg_loads_it and
    # test_a_page_answered_where_a_feed_was_is_never_read_as_an_empty_feed.
    "FeedNotices": True,
    "GeofabrikExtracts": True,
    "GisFile": False,
    "GuidePages": False,
    "HydrographyWatch": False,
    "JsonFeatures": True,
    "MediawikiAnnouncements": True,
    "MediawikiTemplatePages": True,
    # test_extract_json_apis.py: test_a_status_map_with_no_placemarks_is_a_broken_read_not_every_closure_lifted.
    "MyMapsPlacemarks": True,
    # test_extract_json_apis.py: test_a_park_list_with_no_alerts_loads_an_empty_table_beside_the_apis_own_total_of_zero
    # and test_an_nps_answer_without_a_total_refuses_rather_than_proving_a_zero.
    "NpsAlerts": True,
    "NpsContent": True,
    # test_extract_json_apis.py: test_a_road_feed_with_no_events_is_a_proven_zero_and_one_that_is_not_a_feature_collection_refuses.
    "NpsRoadEvents": True,
    # test_extract_run.py: test_a_quiet_hour_from_nws_lands_as_an_empty_warnings_table_with_every_column.
    "NwsAlerts": True,
    "OgcFeatures": True,
    "OpentrailFeed": False,
    "PageNotice": False,
    "PagePoints": False,
    "PdfPoints": False,
    # test_extract_content.py: test_a_feeds_item_count_is_its_proof_and_an_empty_channel_is_a_proven_zero.
    "PodcastEpisodes": True,
    "PodcastFeed": True,
    "PublishedHikes": True,
    "ReviewedDir": True,
    # test_extract_run.py: test_an_empty_reviewed_file_lands_as_an_empty_table and
    # test_a_reviewed_file_that_is_missing_is_unknown_not_empty.
    "ReviewedFile": True,
    # test_extract_json_apis.py: test_a_sheet_that_lost_its_segment_header_or_its_segments_refuses.
    "SheetCsvSegments": False,
    "SiteTerms": True,
    "SocrataDataset": True,
    "UsgsElevatedVolcanoes": True,
    "WordpressChildPages": True,
    "WordpressPosts": True,
    # test_extract_run.py: test_wordpress_terms_are_their_own_daily_table_and_an_empty_vocabulary_is_refused.
    "WordpressTerms": True,
}

#: The registry key every kind is built on for the run check's own test (test 2).
ZERO_KEY = "zero_test"
OGC_ITEMS = "https://ogc.example.org/collections/closures/items"
JSON_POINTS = "https://api.example.org/points"
JSON_PAGED = "https://api.example.org/paged"
GEOFABRIK = "https://download.geofabrik.de/north-america/us"
POINTS_PAGE = "https://club.example.org/water-caches/"
POINTS_PDF = "https://club.example.org/files/water-caches.pdf"
TRAIL_FILE = "https://club.example.org/files/closed-trails.geojson"
STATES = ("georgia", "maine")


def reader_kinds() -> list[type[Resource]]:
    """Every concrete Resource subclass the extract package defines: each `extract._*` module's own public classes."""
    found = []
    for module in pkgutil.iter_modules(extract.__path__):
        if not module.name.startswith("_"):
            continue
        loaded = importlib.import_module(f"extract.{module.name}")
        found += [
            cls
            for name, cls in vars(loaded).items()
            if inspect.isclass(cls)
            and issubclass(cls, Resource)
            and cls is not Resource
            and cls.__module__ == loaded.__name__
            and not name.startswith("_")
        ]
    return sorted(found, key=lambda cls: cls.__name__)


KINDS = reader_kinds()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding one row for every read below, in place of the real one."""
    path = tmp_path / "sources.json"
    sources = [
        {"key": ZERO_KEY, "url": "https://example.org/zero/"},
        {"key": "alerts", "url": "https://club.example.org/category/trail-alerts/", "kind": "published_notices"},
        {
            "key": "greenways",
            "url": "https://data.example.gov/d/abcd-1234",
            "kind": "socrata_geojson_layer",
            "domain": "data.example.gov",
            "dataset_id": "abcd-1234",
            "where": GREENWAY_WHERE,
            "crawl_delay": 1,
        },
        {"key": "usgs_elevated_volcanoes", "url": VOLCANOES},
        {"key": "tehcc_wiki_announcements", "url": WIKI, "template": "Template:Announcement"},
        {"key": "ogc_closures", "url": OGC_ITEMS},
        {"key": "json_points", "url": JSON_POINTS, "lat_field": "lat", "lon_field": "lon"},
        {
            "key": "json_paged",
            "url": JSON_PAGED,
            "paging": "start_limit",
            "items_field": "data",
            "key_fields": ["id"],
            "lat_field": "lat",
            "lon_field": "lon",
        },
        {"key": "osm_water", "url": f"{GEOFABRIK}/", "kind": "geofabrik_extract"},
        {"key": "club_page_points", "url": POINTS_PAGE, "may_be_empty": True},
        {"key": "club_pdf_points", "url": POINTS_PDF, "may_be_empty": True},
        {"key": "club_trail_file", "url": TRAIL_FILE, "file_format": "geojson", "may_be_empty": True},
    ]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """No host is asked anything, so no gate, gap or retry waits, and no answer or gate is left from another test."""
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(_notices, "_GATES", {})
    monkeypatch.setattr(_json_apis, "POLITE_GAP_SECONDS", 0)
    monkeypatch.setattr(_json_apis, "_LAST_REQUEST_END", {})
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(_geofabrik.time, "sleep", lambda seconds: None)
    _notices._ANSWERS.clear()
    yield
    _notices._ANSWERS.clear()


def run_check_of(resource: Resource, rows: list, proofs: dict[str, int], previous: dict[str, int] | None = None) -> list:
    """extract/_run.py's run check on one resource's read: [] when its table may load, else why not."""
    landed = {resource.table: len(rows)} if rows else {}
    return run_check([Planned(resource, Freshness.STALE, None, None)], landed, proofs, previous or {})


# --- 1. The table: every kind says whether it reads the upstream's own count -------------------------------------


def test_every_reader_kind_is_in_the_zero_proof_table_and_declares_its_answer_on_its_own_class():
    """A new reader kind is refused until somebody writes down whether its count is the upstream's own: inheriting the
    answer would let a subclass that reads differently prove a zero with its parent's words."""
    assert {kind.__name__ for kind in KINDS} == set(READS_UPSTREAM_COUNT), "add the kind to READS_UPSTREAM_COUNT"
    undeclared = sorted(kind.__name__ for kind in KINDS if "zero_proof" not in vars(kind))
    assert undeclared == [], "declare zero_proof on the kind's own class, a string naming the count or None"


@pytest.mark.parametrize("kind", KINDS, ids=lambda kind: kind.__name__)
def test_a_kinds_zero_proof_is_a_named_count_exactly_where_the_table_says_it_reads_one(kind, registry):
    proof = kind(key=ZERO_KEY, club="testclub", type="closures").zero_proof
    if READS_UPSTREAM_COUNT[kind.__name__]:
        assert isinstance(proof, str) and proof.strip(), f"{kind.__name__} reads the upstream's count: name it"
    else:
        assert proof is None


# --- 2. The run check, kind by kind --------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [kind for kind in KINDS if kind.__name__ != "CatalogueRow"], ids=lambda kind: kind.__name__)
def test_each_kinds_zero_fails_without_a_count_and_passes_beside_a_zero_only_from_the_upstream(kind, registry):
    """Every kind as a closures table: no count refuses its zero; a count of 0 lets it land only where that count is the
    upstream's own, and a kind that counts what it parsed is refused, its zero unknown."""
    resource = kind(key=ZERO_KEY, club="testclub", type="closures")
    table = resource.table

    (unproved,) = run_check_of(resource, [], {})
    assert "0 rows and no upstream count read this run" in unproved

    beside_zero = run_check_of(resource, [], {table: 0})
    if READS_UPSTREAM_COUNT[kind.__name__]:
        assert beside_zero == []
    else:
        (refused,) = beside_zero
        assert f"a {kind.__name__} reads no upstream count that can prove a zero" in refused


@pytest.mark.parametrize("kind", [kind for kind in KINDS if kind.__name__ != "CatalogueRow"], ids=lambda kind: kind.__name__)
def test_a_may_be_empty_table_shrinks_past_the_floor_only_where_its_kind_reads_the_upstreams_count(kind, registry):
    """Closures have no shrink floor because the upstream's own count tells closures lifted from a read cut short. A
    kind whose count is its own parse cannot tell them apart, so its table keeps the floor every other table has."""
    resource = kind(key=ZERO_KEY, club="testclub", type="closures")
    shrunk, prior = 2, 10
    assert shrunk < COLLAPSE_FLOOR * prior

    problems = run_check_of(resource, [{}] * shrunk, {resource.table: shrunk}, {resource.table: prior})

    if READS_UPSTREAM_COUNT[kind.__name__]:
        assert problems == []
    else:
        assert problems == [f"{resource.table}: {shrunk} rows against {prior} last time, below the 50% floor"]


def test_the_catalogue_row_is_held_to_one_row_per_club_whatever_any_count_says(registry):
    resource = _kinds.CatalogueRow(key="reference/trail_orgs.json", club="testclub", type="org")
    assert resource.table == ORGS_TABLE
    (problem,) = run_check_of(resource, [], {ORGS_TABLE: 0})
    assert "0 rows for 1 managing clubs; each club's catalogue row is exactly one" in problem


# --- 3. The reads: each kind whose own zero had no test ------------------------------------------------------------


def test_a_wordpress_category_with_no_post_is_a_proven_zero_by_the_sites_x_wp_total_of_0(registry, requests_mock):
    FakeWordpress(requests_mock, [])
    resource = WordpressPosts(key="alerts", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_testclub__alerts": 0}
    assert run_check_of(resource, rows, proofs) == []


def test_a_wordpress_answer_with_no_x_wp_total_proves_no_zero_and_the_run_check_refuses_it(registry, requests_mock):
    """A cache or proxy that drops the header leaves an empty list with nothing to tell it from a broken route."""
    requests_mock.get(WP + "/categories", json=[{"id": 6, "slug": "trail-alerts"}])
    requests_mock.get(WP + "/posts", json=[])
    resource = WordpressPosts(key="alerts", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {}
    (refused,) = run_check_of(resource, rows, proofs)
    assert "0 rows and no upstream count read this run" in refused


def test_a_socrata_filter_matching_no_row_is_a_proven_zero_by_the_portals_count_of_0(registry, requests_mock):
    FakeSocrata(requests_mock, [], count=0)
    resource = SocrataDataset(key="greenways", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_testclub__greenways": 0}
    assert run_check_of(resource, rows, proofs) == []


def test_a_socrata_count_that_answers_nothing_proves_no_zero_and_the_run_check_refuses_it(registry, requests_mock):
    requests_mock.get(SOCRATA + ".json", json=[])
    requests_mock.get(SOCRATA + ".geojson", json={"type": "FeatureCollection", "features": []})
    resource = SocrataDataset(key="greenways", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {}
    (refused,) = run_check_of(resource, rows, proofs)
    assert "0 rows and no upstream count read this run" in refused


def test_usgs_listing_no_elevated_volcano_is_a_proven_zero_and_an_answer_that_is_not_a_list_raises(registry, requests_mock):
    resource = UsgsElevatedVolcanoes(key="usgs_elevated_volcanoes", club="usgs", type="warnings")
    requests_mock.get(VOLCANOES, json=[])
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_usgs__usgs_elevated_volcanoes": 0}
    assert run_check_of(resource, rows, proofs) == []
    requests_mock.get(VOLCANOES, json={"message": "Service Unavailable"})
    with pytest.raises(ValueError, match="not a list of volcanoes"):
        list(resource.rows({}))


def test_a_wiki_template_nothing_carries_is_a_proven_zero_once_the_listing_says_batchcomplete(registry, requests_mock):
    FakeWiki(requests_mock, [])
    resource = MediawikiAnnouncements(key="tehcc_wiki_announcements", club="tehcc", type="warnings")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_tehcc__tehcc_wiki_announcements": 0}
    assert run_check_of(resource, rows, proofs) == []


def test_a_wiki_listing_that_ends_without_batchcomplete_raises_rather_than_proving_a_zero(registry, requests_mock):
    def answer(request, context):
        if "titles" in request.qs:
            return {"batchcomplete": True, "query": {"pages": [{"ns": 10, "title": "Template:Announcement", "pageid": 9}]}}
        return {"query": {"pages": []}}  # neither `continue` nor `batchcomplete`: the listing may be short

    requests_mock.get(WIKI, json=answer)
    resource = MediawikiAnnouncements(key="tehcc_wiki_announcements", club="tehcc", type="warnings")

    with pytest.raises(RuntimeError, match="without batchcomplete"):
        list(resource.rows({}))


def test_an_ogc_collection_matching_nothing_is_a_proven_zero_by_its_own_number_matched(registry, requests_mock):
    requests_mock.get(OGC_ITEMS, json={"type": "FeatureCollection", "numberMatched": 0, "features": [], "links": []})
    resource = OgcFeatures(key="ogc_closures", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_testclub__ogc_closures": 0}
    assert run_check_of(resource, rows, proofs) == []


def test_an_ogc_answer_without_number_matched_proves_no_zero_and_the_run_check_refuses_it(registry, requests_mock):
    requests_mock.get(OGC_ITEMS, json={"type": "FeatureCollection", "features": [], "links": []})
    resource = OgcFeatures(key="ogc_closures", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {}
    (refused,) = run_check_of(resource, rows, proofs)
    assert "0 rows and no upstream count read this run" in refused


def test_a_single_json_answer_listing_nothing_is_a_proven_zero_by_its_own_list(registry, requests_mock):
    requests_mock.get(JSON_POINTS, json=[])
    resource = JsonFeatures(key="json_points", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_testclub__json_points": 0}
    assert run_check_of(resource, rows, proofs) == []


def test_a_paged_json_api_with_no_total_field_proves_no_zero_and_the_run_check_refuses_it(registry, requests_mock):
    requests_mock.get(JSON_PAGED, json={"data": []})
    resource = JsonFeatures(key="json_paged", club="testclub", type="closures")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {}
    (refused,) = run_check_of(resource, rows, proofs)
    assert "0 rows and no upstream count read this run" in refused


@pytest.fixture
def osm_store(tmp_path):
    """A local raw store bound as a running lane binds R2's, as tests/test_extract_geofabrik.py's `store` binds it."""
    fs, root = fsspec.filesystem("file"), str(tmp_path / "raw-store")
    bind_store(fs, root)
    yield fs, root
    unbind_store()


def geofabrik_failing(requests_mock) -> GeofabrikExtracts:
    """Geofabrik allowing every agent, and every state's download answering 404, so no copy lands this run."""
    requests_mock.get("https://download.geofabrik.de/robots.txt", text="User-agent: *\nDisallow:\n")
    for state in STATES:
        requests_mock.get(f"{GEOFABRIK}/{geofabrik.extract_name(state)}", status_code=404)
    return GeofabrikExtracts(key="osm_water", club="osm", type="points_of_interest", states=STATES)


def test_a_first_run_whose_downloads_all_fail_is_a_proven_zero_by_the_stores_own_empty_index(registry, osm_store, requests_mock):
    resource = geofabrik_failing(requests_mock)
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_osm__osm_water": 0}
    assert run_check_of(resource, rows, proofs) == []


def test_a_store_index_that_will_not_parse_proves_no_zero_and_the_run_check_refuses_it(registry, osm_store, requests_mock):
    """The index describes copies the store may hold all fourteen of; unreadable, it says nothing, never "none"."""
    fs, root = osm_store
    fs.makedirs(f"{root}/{CURRENT_PREFIX}", exist_ok=True)
    with fs.open(f"{root}/{CURRENT_PREFIX}/{INDEX_NAME}", "w") as handle:
        handle.write('{"files": {"osm/georgia-latest.osm.pbf": ')  # cut off mid-object
    resource = geofabrik_failing(requests_mock)
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {}
    (refused,) = run_check_of(resource, rows, proofs)
    assert "0 rows and no upstream count read this run" in refused


def test_a_page_whose_parser_finds_no_point_records_its_own_zero_which_proves_nothing(registry, requests_mock, monkeypatch):
    """`may_be_empty` on the row lets the read return no point; the zero it counts is its parser's, so it is refused."""
    monkeypatch.setitem(_pages_points.PAGE_PARSERS, "club_page_points", lambda page, link: [])
    requests_mock.get(
        POINTS_PAGE, text="<html><body><p>Caches are stocked.</p></body></html>", headers={"Content-Type": "text/html"}
    )
    resource = PagePoints(key="club_page_points", club="testclub", type="points_of_interest")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_testclub__club_page_points": 0} and resource.may_be_empty
    (refused,) = run_check_of(resource, rows, proofs)
    assert "a PagePoints reads no upstream count that can prove a zero" in refused


def test_a_pdf_whose_parser_reads_no_point_records_its_own_zero_which_proves_nothing(registry, requests_mock, monkeypatch):
    monkeypatch.setitem(_pdf_points.PDF_PARSERS, "club_pdf_points", lambda texts: [])
    monkeypatch.setattr(fetch_club_pdfs, "extract_page_texts", lambda body: ["Water caches, as of this week"])
    requests_mock.get(POINTS_PDF, content=b"%PDF-1.4 an invented document", headers={"Content-Type": "application/pdf"})
    resource = PdfPoints(key="club_pdf_points", club="testclub", type="points_of_interest")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_testclub__club_pdf_points": 0} and resource.may_be_empty
    (refused,) = run_check_of(resource, rows, proofs)
    assert "a PdfPoints reads no upstream count that can prove a zero" in refused


@pytest.mark.parametrize(
    "document",
    [{"type": "FeatureCollection", "features": []}, {"type": "FeatureCollection"}],
    ids=["an empty collection", "a collection that lost its features key"],
)
def test_a_gis_file_that_parses_to_no_feature_records_its_own_zero_which_proves_nothing(registry, requests_mock, document):
    """A FeatureCollection with no `features` key parses to none, as an empty one does: the count is the reader's."""
    requests_mock.get(TRAIL_FILE, json=document)
    resource = GisFile(key="club_trail_file", club="testclub", type="trail_lines")
    proofs = {}

    rows = list(resource.rows(proofs))

    assert rows == [] and proofs == {"raw_testclub__club_trail_file": 0} and resource.may_be_empty
    (refused,) = run_check_of(resource, rows, proofs)
    assert "a GisFile reads no upstream count that can prove a zero" in refused
