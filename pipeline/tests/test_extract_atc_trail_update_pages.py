"""extract/_kinds.py's AtcTrailUpdatePages: ATC's Trail Updates read off their website, under the socket guard.

The parse is lib/atc_scrape.py's own (tests/test_lib_atc_scrape.py holds it),
so these are about what the resource adds around it (CL11, #1793 stage 3):
every request names the project and waits ATC's Crawl-delay; the change check
is the sitemap's (slug, lastmod) set and is never FRESH on a read it could not
make; one page that does not parse refuses the whole read, so the last
committed table stands; the proof is the sitemap's own slug count; and ATC's
prose never lands. requests_mock answers every URL, so nothing reaches ATC.
"""

import json

import pytest
from dlt.pipeline.exceptions import PipelineStepFailed

import make_dbt_fixtures
from extract._contract import discover
from extract._kinds import ATC_CRAWL_DELAY_SECONDS, AtcTrailUpdatePages, atc_trail_update_pages
from lib import http_retry
from lib.atc_scrape import LISTING_URL, listing_url, update_url
from lib.freshness_state import Freshness
from lib.user_agent import USER_AGENT
from tests.test_extract_run import lane, warehouse

SITEMAP_URL = "https://appalachiantrail.org/trail-updates-sitemap.xml"
BODY = "Fixture prose that is ATC's own words and must never land."


def page(title: str, modified: str = "2026-09-03T15:54:14-04:00", chip: str = "VA | Closure", mile: str = "NOBO mile 670.2"):
    """One update page in the shape lib/atc_scrape.py reads (tests/test_lib_atc_scrape.py's page())."""
    return (
        f"<html><head><title>{title} - Appalachian Trail Conservancy</title>"
        f'<script type="application/ld+json">{{"dateModified":"{modified}","datePublished":"2026-08-01T09:00:00-04:00"}}</script>'
        "</head><body><main><nav><a>Maine</a></nav><a>Privacy Policy</a>"
        f"<h1>{title}</h1><span>{chip}</span><span>4 DAYS AGO</span><p>{BODY} ({mile}).</p>"
        "<h2>Stay Connected</h2></main></body></html>"
    )


def sitemap(*entries: tuple[str, str]) -> str:
    urls = "".join(f"<url><loc><![CDATA[{loc}]]></loc><lastmod><![CDATA[{lastmod}]]></lastmod></url>" for loc, lastmod in entries)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


@pytest.fixture
def sleeps(monkeypatch):
    """Every wait lib/http_retry.py asks for, recorded rather than slept."""
    waited = []
    monkeypatch.setattr(http_retry.time, "sleep", waited.append)
    return waited


@pytest.fixture
def atc(requests_mock):
    """ATC's site with two updates, a point and a range written with thousands separators."""

    def serve(entries=None, pages=None):
        entries = entries or [
            (update_url("first-update"), "2026-09-03T19:54:14+00:00"),
            (update_url("second-update"), "2026-09-01T12:00:00+00:00"),
        ]
        pages = pages or {
            "first-update": page("Fixture VA: First Update"),
            "second-update": page("Fixture CT: Second Update", chip="CT | Water", mile="NOBO mile 1,503.6 to 1,510"),
        }
        requests_mock.get(SITEMAP_URL, text=sitemap(*entries), headers={"Content-Type": "text/xml"})
        for slug, html in pages.items():
            requests_mock.get(update_url(slug), text=html)
        return requests_mock

    return serve


def resource() -> AtcTrailUpdatePages:
    return AtcTrailUpdatePages(key="atc_trail_updates", club="atc", type="closures")


def read(proofs=None) -> list[dict]:
    return list(resource().rows({} if proofs is None else proofs))


def test_atc_closures_py_reads_the_sitemap_beside_its_registry_rows_listing_on_the_hourly_lane():
    (placed,) = [
        r
        for f in discover()
        if f.club == "atc" and f.type == "closures"
        for r in f.resources
        if isinstance(r, AtcTrailUpdatePages)
    ]
    assert placed.sitemap_url == SITEMAP_URL == atc_trail_update_pages("atc_trail_updates").sitemap_url
    assert (placed.table, placed.part, placed.cadence) == ("raw_atc__atc_trail_updates_pages", "pages", "hourly")


def test_every_request_to_atc_names_the_project_and_waits_its_crawl_delay(atc, sleeps):
    """ATC's robots.txt asks for `Crawl-delay: 10`, and its host refuses python-requests' own agent (403)."""
    served = atc()
    resource().change_check(None)
    read()
    sent = served.request_history
    assert len(sent) == 4, "the change check's sitemap, the read's sitemap and the two pages"
    assert {request.headers["User-Agent"] for request in sent} == {USER_AGENT}
    assert sleeps == [ATC_CRAWL_DELAY_SECONDS] * len(sent) and ATC_CRAWL_DELAY_SECONDS == 10


def test_the_change_check_is_fresh_only_while_the_sitemaps_slug_and_lastmod_set_holds(atc, sleeps):
    atc()
    verdict, marker = resource().change_check(None)
    assert verdict is Freshness.STALE and marker["slugs"] == "2"
    assert resource().change_check(marker) == (Freshness.FRESH, marker)

    atc(
        entries=[
            (update_url("first-update"), "2026-09-04T00:00:00+00:00"),
            (update_url("second-update"), "2026-09-01T12:00:00+00:00"),
        ]
    )
    assert resource().change_check(marker)[0] is Freshness.STALE, "an edit moves its lastmod"
    atc(entries=[(update_url("first-update"), "2026-09-03T19:54:14+00:00")])
    assert resource().change_check(marker)[0] is Freshness.STALE, "an update ATC took down leaves the set"


@pytest.mark.parametrize(
    ("status", "text"),
    [(503, "unavailable"), (200, "<html><p>a login page, not a sitemap</html>"), (200, sitemap())],
    ids=["a_failed_request", "a_page_that_is_not_xml", "an_empty_sitemap"],
)
def test_a_sitemap_the_check_cannot_read_is_unknown_never_fresh(requests_mock, sleeps, status, text):
    requests_mock.get(SITEMAP_URL, status_code=status, text=text)
    assert resource().change_check({"slugs": "2", "set_sha256": "x"}) == (Freshness.UNKNOWN, None)


def test_an_empty_sitemap_refuses_the_read_rather_than_proving_a_zero(requests_mock, sleeps):
    """fetch_atc_updates.py's rule: no updates listed is a parse that broke, never "ATC has nothing posted"."""
    requests_mock.get(SITEMAP_URL, text=sitemap())
    with pytest.raises(RuntimeError, match="lists no update"):
        read()


def test_one_page_that_does_not_parse_refuses_the_whole_read(atc, sleeps):
    """TOLERATED_PARSE_FAILURES is zero: the updates that still parsed after a theme change never land alone."""
    atc(pages={"first-update": page("Fixture VA: First Update"), "second-update": "<html><title>Theme changed</title></html>"})
    proofs = {}
    with pytest.raises(RuntimeError, match="1 of 2 update pages did not parse"):
        list(resource().rows(proofs))
    assert proofs == {}, "no count is proved for a read that refused"


def test_a_sitemap_listing_something_other_than_an_update_refuses_the_read(atc, sleeps):
    atc(entries=[("https://appalachiantrail.org/about/", "2026-09-03T19:54:14+00:00")])
    with pytest.raises(ValueError, match="not a trail update's page"):
        read()


def test_the_proof_is_the_sitemaps_own_slug_count_and_a_slug_listed_twice_lands_once(atc, sleeps):
    atc(entries=[(update_url("first-update"), "2026-09-03T19:54:14+00:00")] * 2)
    proofs = {}
    rows = list(resource().rows(proofs))
    assert [row["slug"] for row in rows] == ["first-update"]
    assert proofs == {"raw_atc__atc_trail_updates_pages": 1}


def test_a_mile_written_with_a_thousands_separator_lands_as_the_whole_number(atc, sleeps):
    """`NOBO mile 1,503.6` read without the comma is mile 1, a Connecticut spring drawn in Georgia (CL11)."""
    atc()
    second = next(row for row in read() if row["slug"] == "second-update")
    assert second["miles"] == [{"direction": "NOBO", "start": 1503.6, "end": 1510.0, "raw": "NOBO mile 1,503.6 to 1,510"}]
    assert (second["category"], second["states"], second["date_modified"]) == ("Water", ["CT"], "2026-09-03T15:54:14-04:00")
    assert second["source_url"] == update_url("second-update") and second["sitemap_lastmod"] == "2026-09-01T12:00:00+00:00"


def test_atcs_prose_never_lands(atc, sleeps):
    """sources.json's licence: facts and a link only, so the body text stays on ATC's page."""
    atc()
    for row in read():
        assert "text" not in row
        assert BODY not in json.dumps(row)


def test_a_read_that_refuses_keeps_the_last_committed_table(atc, sleeps, store):
    """A lane run that refuses loads nothing, so the warehouse still serves the last good read, as today's cache does."""
    atc()
    lane(store, resource())
    atc(
        entries=[
            (update_url("first-update"), "2026-09-05T00:00:00+00:00"),
            (update_url("second-update"), "2026-09-01T12:00:00+00:00"),
        ],
        pages={"first-update": "<html>no title at all</html>", "second-update": page("Fixture CT: Second Update")},
    )
    with pytest.raises(PipelineStepFailed, match="did not parse"):
        lane(store, resource())
    con, counts = warehouse(store)
    assert counts["raw_atc__atc_trail_updates_pages"] == 2
    assert {slug for (slug,) in con.execute("select slug from raw.raw_atc__atc_trail_updates_pages").fetchall()} == {
        "first-update",
        "second-update",
    }


def test_make_dbt_fixtures_serves_the_urls_the_resource_and_fetch_atc_updates_ask_for():
    """make_dbt_fixtures.py writes ATC's URLs out, because it imports nothing; these are the code's own."""
    assert make_dbt_fixtures.ATC_TRAIL_UPDATES_URL == LISTING_URL == listing_url(1)
    assert make_dbt_fixtures.ATC_TRAIL_UPDATES_SITEMAP_URL == atc_trail_update_pages("atc_trail_updates").sitemap_url
    answers = make_dbt_fixtures._atc_trail_updates()["answers"]
    pages = {update_url(slug) for slug, *_ in make_dbt_fixtures.ATC_FIXTURE_UPDATES}
    assert set(answers) == {make_dbt_fixtures.ATC_TRAIL_UPDATES_SITEMAP_URL, listing_url(1), listing_url(2), *pages}
