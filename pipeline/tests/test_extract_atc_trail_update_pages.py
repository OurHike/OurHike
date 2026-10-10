"""extract/_kinds.py's AtcTrailUpdatePages: ATC's Trail Updates read off their website, under the socket guard.

The parse is lib/atc_scrape.py's own (tests/test_lib_atc_scrape.py holds it),
so these are about what the resource adds around it (CL11, #1793 stage 3):
every request names the project and waits ATC's Crawl-delay, a retry and a
failure included; the change check reads the sitemap's (slug, lastmod) set and
is never FRESH; a read reads only the pages that are new or whose lastmod
moved, carries the rest from the last committed load, drops what the sitemap
no longer lists and lands the whole set, equal to a full read of the same
pages; a read that runs out of budget lands nothing, keeps what it read, and
completes over later runs; one page that does not parse refuses the whole
read, so the last committed table stands; the proof is the sitemap's own slug
count, which the landed rows must equal; and ATC's prose never lands.
requests_mock answers every URL, so nothing reaches ATC, and a fake clock
stands in for the 10-second waits, so none is slept.
"""

import json
import math

import duckdb
import pytest
from dlt.pipeline.exceptions import PipelineStepFailed

import make_dbt_fixtures
from extract import _kinds
from extract._contract import Carried, Incomplete, discover
from extract._kinds import (
    ATC_CRAWL_DELAY_SECONDS,
    ATC_CRAWL_GATE,
    ATC_PAGE_FACTS,
    ATC_REVALIDATION_RUNS,
    AtcTrailUpdatePages,
    atc_trail_update_pages,
    page_behind_sitemap,
)
from extract._run import (
    INCOMPLETE,
    PROGRESS_TABLE,
    Planned,
    make_pipeline,
    progress_after,
    run_check,
    run_log_rows,
    run_pipeline,
    stored_progress,
    summary_markdown,
)
from extract._warehouse import load_warehouse
from lib import http_retry
from lib.atc_scrape import LISTING_URL, listing_url, update_url
from lib.freshness_state import Freshness
from lib.user_agent import USER_AGENT
from tests.test_extract_conditions_legs import nynjtc_alerts
from tests.test_extract_run import lane, warehouse

SITEMAP_URL = "https://appalachiantrail.org/trail-updates-sitemap.xml"
TABLE = "raw_atc__atc_trail_updates_pages"
BODY = "Fixture prose that is ATC's own words and must never land."
# When a page was read, and dlt's own columns, are the only columns a carried row and a re-read one may differ in.
NOT_FACTS = ("page_fetched_at", "_loaded_at", "_dlt_load_id", "_dlt_id")


def page(
    title: str,
    modified: str = "2026-09-03T15:54:14-04:00",
    chip: str = "VA | Closure",
    mile: str = "NOBO mile 670.2",
    published: str = "2026-08-01T09:00:00-04:00",
):
    """One update page in the shape lib/atc_scrape.py reads (tests/test_lib_atc_scrape.py's page())."""
    return (
        f"<html><head><title>{title} - Appalachian Trail Conservancy</title>"
        f'<script type="application/ld+json">{{"dateModified":"{modified}","datePublished":"{published}"}}</script>'
        "</head><body><main><nav><a>Maine</a></nav><a>Privacy Policy</a>"
        f"<h1>{title}</h1><span>{chip}</span><span>4 DAYS AGO</span><p>{BODY} ({mile}).</p>"
        "<h2>Stay Connected</h2></main></body></html>"
    )


def sitemap(*entries: tuple[str, str]) -> str:
    urls = "".join(f"<url><loc><![CDATA[{loc}]]></loc><lastmod><![CDATA[{lastmod}]]></lastmod></url>" for loc, lastmod in entries)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


@pytest.fixture(autouse=True)
def fresh_gate(monkeypatch):
    """Each test starts with no request sent and no sitemap kept: the gate and the change check's sitemap are module state."""
    monkeypatch.setattr(ATC_CRAWL_GATE, "finished", None)
    monkeypatch.setattr(ATC_CRAWL_GATE, "clock", None)
    monkeypatch.setattr(ATC_CRAWL_GATE, "sleep", None)
    monkeypatch.setattr(_kinds, "_ATC_LISTINGS", {})


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


@pytest.fixture
def sleeps(monkeypatch):
    """Every wait lib/http_retry.py and the Crawl-delay ask for, recorded rather than slept."""
    waited = []
    monkeypatch.setattr(http_retry.time, "sleep", waited.append)
    return waited


class FakeClock:
    """A monotonic clock that only a wait moves, and that a request moves by `request_seconds`."""

    def __init__(self, request_seconds: float = 0.5):
        self.now, self.request_seconds = 1000.0, request_seconds
        self.waits: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(http_retry.time, "sleep", fake.sleep)
    monkeypatch.setattr(ATC_CRAWL_GATE, "clock", fake.clock)
    return fake


class Site:
    """ATC's site under requests_mock: the sitemap and each update's page, every request timed on the fake clock."""

    def __init__(self, requests_mock, clock: FakeClock | None = None):
        self.mock, self.clock = requests_mock, clock
        # (url, started, finished) on the fake clock, for every request answered.
        self.spans: list[tuple[str, float, float]] = []

    def answer(self, body: str):
        def respond(request, context):
            started = self.clock.now if self.clock else 0.0
            if self.clock:
                self.clock.now += self.clock.request_seconds
            self.spans.append((request.url, started, self.clock.now if self.clock else 0.0))
            return body

        return respond

    def serve(self, updates: dict[str, tuple[str, str]], *, flaky: tuple[str, ...] = ()) -> "Site":
        """`updates` is {slug: (lastmod, page html)}, in the sitemap's order. A `flaky` slug answers 503 once first."""
        entries = [(update_url(slug), lastmod) for slug, (lastmod, _) in updates.items()]
        self.mock.get(SITEMAP_URL, text=self.answer(sitemap(*entries)), headers={"Content-Type": "text/xml"})
        for slug, (_, html) in updates.items():
            ok = {"text": self.answer(html)}
            self.mock.get(update_url(slug), [{"status_code": 503, "text": self.answer("busy")}, ok] if slug in flaky else [ok])
        return self

    def pages_read(self) -> list[str]:
        return [url.rsplit("/", 2)[-2] for url, *_ in self.spans if url != SITEMAP_URL]

    def sitemaps_read(self) -> int:
        return sum(url == SITEMAP_URL for url, *_ in self.spans)

    def forget(self) -> None:
        self.spans.clear()


def updates(*slugs: str, lastmod: str = "2026-09-03T19:54:14+00:00") -> dict[str, tuple[str, str]]:
    """Each slug as an update page whose own dateModified is its sitemap lastmod, as on ATC's site (85 of 86)."""
    return {slug: (lastmod, page(f"Fixture VA: {slug}", modified=lastmod)) for slug in slugs}


def decoded(rows) -> list[dict]:
    """Warehouse rows with their JSON columns read back into lists, to compare with the rows a read yields."""
    return [{**row, **{name: json.loads(row[name]) for name in ("states", "miles")}} for row in rows]


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


def read_carried(carried: Carried, proofs=None) -> list[dict]:
    resource().change_check(None)
    return list(resource().rows_carried({} if proofs is None else proofs, carried))


def facts(rows) -> list[dict]:
    """Rows without when they were read, keyed and ordered by slug: what a carried row and a re-read one share."""
    return sorted(({k: v for k, v in row.items() if k not in NOT_FACTS} for row in rows), key=lambda row: row["slug"])


def table(store_or_leg) -> list[dict]:
    """The warehouse's ATC pages table, every column, as plain rows."""
    con, _ = store_or_leg
    cursor = con.execute(f"select * from raw.{TABLE} order by _row")
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


def leg(store, *resources, read_seconds=None):
    return run_pipeline(
        "conditions_ua",
        store["bucket_url"],
        resources=list(resources),
        pipelines_dir=store["pipelines_dir"],
        read_seconds=read_seconds,
    )


def leg_warehouse(store):
    con = duckdb.connect()
    counts = load_warehouse(con, make_pipeline("conditions_ua", store["bucket_url"], store["pipelines_dir"]))
    return con, counts


def test_atc_closures_py_reads_the_sitemap_beside_its_registry_rows_listing_on_the_hourly_lane():
    (placed,) = [
        r
        for f in discover()
        if f.club == "atc" and f.type == "closures"
        for r in f.resources
        if isinstance(r, AtcTrailUpdatePages)
    ]
    assert placed.sitemap_url == SITEMAP_URL == atc_trail_update_pages("atc_trail_updates").sitemap_url
    assert (placed.table, placed.part, placed.cadence) == (TABLE, "pages", "hourly")
    assert placed.carries and placed.exact_proof


def test_no_two_requests_to_atc_are_closer_than_its_crawl_delay_across_the_check_the_read_and_a_retry(requests_mock, clock):
    """ATC's robots.txt asks for `Crawl-delay: 10`, and its host refuses python-requests' own agent (403).

    Measured end to start, so a request that took a while still leaves the full 10 s after it; a 503 that
    lib/http_retry.py retries after its own 5 s still waits the rest; and the read after the change check
    reuses the check's sitemap rather than asking for it twice.
    """
    site = Site(requests_mock, clock).serve(updates("first-update", "second-update", "third-update"), flaky=("second-update",))
    resource().change_check(None)
    read()

    assert [url for url, *_ in site.spans].count(SITEMAP_URL) == 1
    assert site.pages_read() == ["first-update", "second-update", "second-update", "third-update"]
    gaps = [later[1] - earlier[2] for earlier, later in zip(site.spans, site.spans[1:])]
    assert len(gaps) == 4 and min(gaps) >= ATC_CRAWL_DELAY_SECONDS - 1e-9 and ATC_CRAWL_DELAY_SECONDS == 10
    assert {request.headers["User-Agent"] for request in requests_mock.request_history} == {USER_AGENT}


def test_a_budget_ends_the_read_before_it_ever_shortens_the_crawl_delay(requests_mock, clock):
    """A read with 60 s fits three pages 10 s apart and stops; it never fits a fourth by asking sooner."""
    site = Site(requests_mock, clock).serve(updates(*(f"update-{n}" for n in range(6))))
    with pytest.raises(Incomplete) as stopped:
        read_carried(Carried(seconds=60))
    assert (stopped.value.read, stopped.value.needed) == (3, 3)
    gaps = [later[1] - earlier[2] for earlier, later in zip(site.spans, site.spans[1:])]
    assert min(gaps) >= ATC_CRAWL_DELAY_SECONDS - 1e-9
    assert clock.now - site.spans[0][1] < 60, "the read returned inside its budget, so read_each never abandons it"


def test_the_change_check_is_never_fresh_and_its_marker_moves_with_the_sitemaps_slug_and_lastmod_set(atc, sleeps):
    """Every run has pages to re-read ("LASTMOD IS NOT EVERY CHANGE"), so the check never leaves the read out."""
    atc()
    verdict, marker = resource().change_check(None)
    assert verdict is Freshness.STALE and marker["slugs"] == "2"
    assert resource().change_check(marker) == (Freshness.STALE, marker)

    atc(
        entries=[
            (update_url("first-update"), "2026-09-04T00:00:00+00:00"),
            (update_url("second-update"), "2026-09-01T12:00:00+00:00"),
        ]
    )
    assert resource().change_check(marker)[1] != marker, "an edit moves its lastmod"
    atc(entries=[(update_url("first-update"), "2026-09-03T19:54:14+00:00")])
    assert resource().change_check(marker)[1]["slugs"] == "1", "an update ATC took down leaves the set"


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
    assert proofs == {TABLE: 1}


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
    assert counts[TABLE] == 2
    assert {slug for (slug,) in con.execute(f"select slug from raw.{TABLE}").fetchall()} == {"first-update", "second-update"}


# What moved is read, and nothing else: each case against the rows a first read committed.


def first_read(requests_mock, clock, *slugs):
    """A full read of `slugs`, as the committed load a later read carries from, and the site serving it."""
    site = Site(requests_mock, clock).serve(updates(*slugs))
    committed = tuple(read_carried(Carried()))
    site.forget()
    return site, committed


def test_a_page_whose_lastmod_moved_is_read_again_and_its_new_facts_land(requests_mock, clock):
    site, committed = first_read(requests_mock, clock, "a", "b", "c")
    moved = updates("a", "b", "c")
    moved["b"] = ("2026-09-20T10:00:00+00:00", page("Fixture VA: b reopened", modified="2026-09-20T10:00:00+00:00"))
    site.serve(moved)

    rows = read_carried(Carried(committed=committed))

    assert site.pages_read()[0] == "b", "the moved page first, before any re-read the budget allows"
    b = next(row for row in rows if row["slug"] == "b")
    assert (b["title"], b["sitemap_lastmod"]) == ("Fixture VA: b reopened", "2026-09-20T10:00:00+00:00")


def test_a_page_whose_lastmod_holds_is_carried_from_the_committed_load_unread(requests_mock, clock):
    site, committed = first_read(requests_mock, clock, *(f"u{n}" for n in range(30)))
    site.serve(updates(*(f"u{n}" for n in range(30))))

    rows = read_carried(Carried(committed=committed))

    share = math.ceil(30 / ATC_REVALIDATION_RUNS)
    assert len(site.pages_read()) == share == 2, "only the re-read share, of 30 pages nothing moved on"
    assert facts(rows) == facts({**row, "_row": n} for n, row in enumerate(committed))
    carried = [row for row in rows if row["slug"] not in site.pages_read()]
    assert len(carried) == 28 and all(row in committed for row in carried), "each the committed row itself, read time and all"


def test_an_update_the_sitemap_stops_listing_is_dropped_and_lands_nowhere(requests_mock, clock):
    site, committed = first_read(requests_mock, clock, "a", "b", "c")
    site.serve(updates("a", "c"))
    proofs = {}

    rows = read_carried(Carried(committed=committed), proofs)

    assert [row["slug"] for row in rows] == ["a", "c"] and [row["_row"] for row in rows] == [0, 1]
    assert proofs == {TABLE: 2}
    assert "b" not in site.pages_read()


def test_a_new_update_in_the_sitemap_is_read_before_the_set_lands(requests_mock, clock):
    site, committed = first_read(requests_mock, clock, "a", "b")
    site.serve(updates("new-closure", "a", "b"))

    rows = read_carried(Carried(committed=committed))

    assert site.pages_read()[0] == "new-closure"
    assert [row["slug"] for row in rows] == ["new-closure", "a", "b"]


def test_a_page_served_older_than_its_lastmod_lands_as_served_and_is_read_again_first(requests_mock, clock, capsys):
    """The sitemap and the pages sit behind separate caches (max-age=600), so a page can lag its own lastmod.

    The row lands as the page said, because the committed row is older still, and the next run re-reads it
    ahead of the pages read longest ago, though its lastmod did not move. Its new facts were expected, so
    they are not reported as a change the lastmod hid.
    """
    stale = page("Fixture VA: a as cached", modified="2026-09-03T19:54:14+00:00")
    site = Site(requests_mock, clock).serve({"a": ("2026-09-20T10:00:00+00:00", stale), **updates("b", "c")})
    (a, *_) = committed = tuple(read_carried(Carried()))
    assert page_behind_sitemap(a) and not any(page_behind_sitemap(row) for row in committed[1:])
    site.forget()

    site.serve(
        {"a": ("2026-09-20T10:00:00+00:00", page("Fixture VA: a now", modified="2026-09-20T10:00:00+00:00")), **updates("b", "c")}
    )
    rows = read_carried(Carried(committed=committed))

    assert site.pages_read()[0] == "a"
    assert rows[0]["title"] == "Fixture VA: a now" and not page_behind_sitemap(rows[0])
    assert "changed without its lastmod" not in capsys.readouterr().out


def test_every_page_is_read_again_within_a_day_of_runs_and_a_change_its_lastmod_hid_is_printed(requests_mock, clock, capsys):
    """WordPress moves no lastmod when a term the chip shows is renamed: the re-read finds it, lands it, and says so."""
    slugs = [f"u{n}" for n in range(48)]
    site, committed = first_read(requests_mock, clock, *slugs)
    renamed = updates(*slugs)
    for slug in slugs:
        lastmod, _ = renamed[slug]
        renamed[slug] = (lastmod, page(f"Fixture VA: {slug}", modified=lastmod, chip="VA | Trail Closure"))
    site.serve(renamed)

    reread: list[str] = []
    rows = list(committed)
    for _ in range(ATC_REVALIDATION_RUNS):
        rows = read_carried(Carried(committed=tuple(rows)))
        reread += site.pages_read()
        site.forget()

    assert sorted(reread) == sorted(slugs), "48 pages, 2 a run, each once in 24 runs"
    assert {row["category"] for row in rows} == {"Trail Closure"}
    assert "changed without its lastmod" in capsys.readouterr().out
    assert set(ATC_PAGE_FACTS) >= {"category", "title", "miles", "states"}


def test_a_read_whose_budget_fits_no_page_raises_rather_than_waiting_forever(requests_mock, clock):
    Site(requests_mock, clock).serve(updates("a", "b"))
    with pytest.raises(RuntimeError, match="fit none of the 2 update pages"):
        read_carried(Carried(seconds=10))


def test_progress_after_drops_a_loaded_reads_progress_replaces_an_incomplete_ones_and_keeps_the_rest():
    class Report:
        progress = {"read_again": [{"slug": "new"}]}

    kept = {"loaded": [{"slug": "a"}], "read_again": [{"slug": "old"}], "refused": [{"slug": "r"}]}
    assert progress_after(kept, Report(), {"loaded"}) == {"read_again": [{"slug": "new"}], "refused": [{"slug": "r"}]}


# The run check: the sitemap's own count, exactly.


def test_the_run_check_refuses_a_landed_count_that_differs_from_the_sitemaps_either_way():
    planned = [Planned(resource(), Freshness.STALE, None, None)]
    assert run_check(planned, {TABLE: 3}, {TABLE: 3}, {}) == []
    (more,) = run_check(planned, {TABLE: 4}, {TABLE: 3}, {})
    assert "4 rows, and the upstream counts 3, which must be exactly" in more
    (fewer,) = run_check(planned, {TABLE: 2}, {TABLE: 3}, {})
    assert "2 rows, and the upstream counts 3" in fewer
    (unproved,) = run_check(planned, {TABLE: 3}, {}, {})
    assert "upstream counts None" in unproved


class CarriesOneTooMany(AtcTrailUpdatePages):
    """A carry that went wrong: one row twice, which the sitemap's count does not hold."""

    def rows_carried(self, proofs, carried):
        rows = list(super().rows_carried(proofs, carried))
        yield from rows
        yield {**rows[0], "_row": len(rows)}


def test_a_lane_whose_landed_rows_outnumber_the_sitemap_is_refused_and_the_last_table_stands(atc, sleeps, store):
    atc()
    lane(store, resource())
    with pytest.raises(Exception, match="3 rows, and the upstream counts 2, which must be exactly"):
        lane(store, CarriesOneTooMany(key="atc_trail_updates", club="atc", type="closures"))
    _, counts = warehouse(store)
    assert counts[TABLE] == 2


# End to end: through dlt, the committed load's Parquet, and the warehouse.


def test_an_incremental_read_after_a_change_lands_the_same_table_as_a_full_read_of_the_same_pages(requests_mock, clock, tmp_path):
    """cw2's parity holds on the carried table: a page carried through the committed load's Parquet, JSON columns
    and all, is the row a full read would land, in the same order, under the same proof."""
    site = Site(requests_mock, clock)
    before = updates("a", "b", "c", "d", "e")
    before["b"] = (before["b"][0], page("Fixture CT: b", chip="CT | Water", mile="NOBO mile 1,503.6 to 1,510"))
    site.serve(before)
    incremental = {"bucket_url": (tmp_path / "incremental").as_uri(), "pipelines_dir": str(tmp_path / "pi")}
    lane(incremental, resource())

    after = dict(before)
    after["c"] = ("2026-09-21T08:00:00+00:00", page("Fixture VA: c reopened", modified="2026-09-21T08:00:00+00:00"))
    del after["d"]
    after = {
        "f-new": ("2026-09-22T08:00:00+00:00", page("Fixture NJ: f", chip="NJ | Detour", modified="2026-09-22T08:00:00+00:00")),
        **after,
    }
    site.serve(after)
    site.forget()
    report = lane(incremental, resource())
    assert sorted(site.pages_read()[:2]) == ["c", "f-new"] and len(site.pages_read()) == 2 + math.ceil(5 / ATC_REVALIDATION_RUNS)

    full = {"bucket_url": (tmp_path / "full").as_uri(), "pipelines_dir": str(tmp_path / "pf")}
    lane(full, resource())

    carried, whole = table(warehouse(incremental)), table(warehouse(full))
    assert [row["slug"] for row in whole] == ["f-new", "a", "b", "c", "e"]
    assert facts(carried) == facts(whole)
    assert report.rows == report.proofs == {TABLE: 5}


def test_a_first_run_lands_nothing_until_every_page_is_read_and_completes_over_several_runs(requests_mock, clock, store):
    """An empty raw store on the conditions leg's budget: 7 pages at 3 a run land after the third run, never part-way.

    Until then the table is named as not yet loaded and built empty, so another club's closures still load and
    the build still runs, and what each run read is kept in _extract_progress, never in the table.
    """
    slugs = [f"u{n}" for n in range(7)]
    site = Site(requests_mock, clock).serve(updates(*slugs))
    pipeline = make_pipeline("conditions_ua", store["bucket_url"], store["pipelines_dir"])

    seen: list[int] = []
    for run in range(3):
        report = leg(store, resource(), nynjtc_alerts(f"n{run}", count=1), read_seconds=60)
        assert report.rows["raw_nynjtc__nynjtc_trail_alerts"] == 1, "the other club loads every run"
        con, counts = leg_warehouse(store)
        if run < 2:
            assert TABLE in report.incomplete and "not yet loaded" in report.incomplete[TABLE]
            assert TABLE not in report.rows and counts[TABLE] == 0
            assert con.execute(f"select count(*) from raw.{TABLE}").fetchone() == (0,), "empty, never part of the set"
            seen.append(len(stored_progress(pipeline)[TABLE]))
            latest = [row for row in run_log_rows(pipeline) if row["run_id"] == report.run_id and row["table_name"] == TABLE]
            assert [row["outcome"] for row in latest] == [INCOMPLETE]
            summary = summary_markdown(report, "conditions_ua")
            assert "**Read incomplete**" in summary and f"| `{TABLE}` | stale | incomplete, nothing landed |  |" in summary
        else:
            assert report.incomplete == {} and report.rows[TABLE] == report.proofs[TABLE] == 7
            assert counts[TABLE] == 7 and stored_progress(pipeline) == {}
    assert seen == [3, 6]
    pages = site.pages_read()
    assert sorted(set(pages)) == slugs and len(pages) == 7 + math.ceil(7 / ATC_REVALIDATION_RUNS)
    full = list(read_carried(Carried()))
    assert facts(decoded(table((con, None)))) == facts(full)


def test_progress_kept_by_a_first_run_survives_a_run_whose_read_failed(requests_mock, clock, store):
    """A 503 from ATC refuses that run's read on its own, and costs the first pass nothing it had already read."""
    slugs = [f"u{n}" for n in range(7)]
    site = Site(requests_mock, clock).serve(updates(*slugs))
    pipeline = make_pipeline("conditions_ua", store["bucket_url"], store["pipelines_dir"])
    leg(store, resource(), read_seconds=60)
    kept = stored_progress(pipeline)[TABLE]

    requests_mock.get(SITEMAP_URL, status_code=503, text="busy")
    report = leg(store, resource(), read_seconds=60)
    assert TABLE in report.isolated
    assert stored_progress(pipeline)[TABLE] == kept

    site.serve(updates(*slugs))
    leg(store, resource(), read_seconds=60)
    assert len(stored_progress(pipeline)[TABLE]) == 6
    assert PROGRESS_TABLE not in leg_warehouse(store)[1], "progress is never read as the data"


def test_make_dbt_fixtures_serves_the_urls_the_resource_and_fetch_atc_updates_ask_for():
    """make_dbt_fixtures.py writes ATC's URLs out, because it imports nothing; these are the code's own."""
    assert make_dbt_fixtures.ATC_TRAIL_UPDATES_URL == LISTING_URL == listing_url(1)
    assert make_dbt_fixtures.ATC_TRAIL_UPDATES_SITEMAP_URL == atc_trail_update_pages("atc_trail_updates").sitemap_url
    answers = make_dbt_fixtures._atc_trail_updates()["answers"]
    pages = {update_url(slug) for slug, *_ in make_dbt_fixtures.ATC_FIXTURE_UPDATES}
    assert set(answers) == {make_dbt_fixtures.ATC_TRAIL_UPDATES_SITEMAP_URL, listing_url(1), listing_url(2), *pages}
