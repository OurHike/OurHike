"""extract/_notices.py's FeedNotices and PageNotice, and the WordpressPosts options decision 53's inventory needs.

Every server here is requests_mock under conftest.py's socket guard, and every
feed, page and post is invented in the shape the inventory read (2026-10-03):
RSS 2.0 as WordPress, BLM's Drupal and Weebly serve it, Atom as Joomla serves
it, WordPress's REST page, a PDF. The cases are the ones decision 53 names: a
304 to a trusted validator is FRESH and never reaches dlt; an unchanged
upstream is left out of the run with its rows standing (the dlt skill's
hazard rule 2); an empty feed proves its own zero; a walled page is UNKNOWN
and its last row stands, never zero; a page with no date lands none; and no
prose and no person lands from either reader (decision 55).
"""

from __future__ import annotations

import json

import duckdb
import pytest

from extract import _kinds, _notices
from extract._kinds import WordpressPosts, feed_notices, page_notice, wordpress_posts
from extract._notices import (
    DATE,
    FEED_COLUMNS,
    PAGE_COLUMNS,
    WINDOW,
    NoticeUnreadable,
    PdfFacts,
    page_stated_date,
    polite,
)
from extract._run import make_pipeline, run_pipeline
from extract._warehouse import load_warehouse
from lib.freshness_state import Freshness
from lib.user_agent import USER_AGENT

FEED_URL = "https://club.example.org/category/trail-alerts/feed/"
BLM_FEED_URL = "https://agency.example.gov/press-release/state/rss"
ATOM_URL = "https://trail.example.org/index.php/section-updates?format=feed&type=atom"
PAGE_URL = "https://club.example.org/trail-conditions/"
WP_PAGE_URL = "https://foothillstrail.org/trail-conditions/"
PDF_URL = "https://club.example.org/wp-content/uploads/hiker-alert.pdf"
WP = "https://club.example.org/wp-json/wp/v2"


@pytest.fixture(autouse=True)
def quiet_gates_and_answers(monkeypatch):
    """No real waiting, and no answer or host gate left over from another test (both live for the process)."""
    paused: list[float] = []
    monkeypatch.setattr(_notices, "_pause", paused.append)
    _notices._ANSWERS.clear()
    _notices._GATES.clear()
    yield paused
    _notices._ANSWERS.clear()
    _notices._GATES.clear()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps(
            {
                "sources": [
                    {"key": "club_alerts_feed", "url": FEED_URL, "kind": "published_notices"},
                    {"key": "agency_press", "url": BLM_FEED_URL, "kind": "published_notices"},
                    {"key": "section_updates", "url": ATOM_URL, "kind": "published_notices"},
                    {"key": "club_conditions", "url": PAGE_URL, "kind": "published_notices", "title": "Trail Conditions"},
                    {"key": "wpstaq_conditions", "url": WP_PAGE_URL, "kind": "published_notices"},
                    {"key": "wpstaq_query", "url": WP_PAGE_URL + "?tab=2", "kind": "published_notices"},
                    {"key": "wpstaq_category", "url": "https://foothillstrail.org/category/alerts/", "kind": "published_notices"},
                    {"key": "hiker_alert_pdf", "url": PDF_URL, "kind": "published_notices", "title": "Hiker Alert: logging"},
                    {"key": "club_closures", "url": "https://club.example.org/category/closures/", "kind": "published_notices"},
                    {"key": "club_alert_type", "url": "https://club.example.org/plan/alerts/", "kind": "published_notices"},
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
    return {"url": (tmp_path / "raw-store").as_uri(), "dir": str(tmp_path / "pipelines")}


def leg(store, *resources):
    """A notices leg, where every club's feed, page and WordPress notices run since decision 61."""
    return run_pipeline("notices_ua", store["url"], resources=list(resources), pipelines_dir=store["dir"])


def landed(store, table: str) -> list[dict]:
    with duckdb.connect() as con:
        load_warehouse(con, make_pipeline("notices_ua", store["url"], store["dir"]))
        cursor = con.execute(f'select * from raw."{table}"')
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def rss(*items: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>Alerts - A Trail Club</title>'
        "<link>https://club.example.org</link><lastBuildDate>Fri, 06 Mar 2026 14:01:24 +0000</lastBuildDate>"
        "<generator>https://wordpress.org/?v=7.1.2</generator>" + "".join(items) + "</channel></rss>"
    ).encode()


def rss_item(post: int, title: str = "Bridge out at Mile 12", when: str = "Sun, 01 Mar 2026 13:52:08 +0000") -> str:
    return (
        f"<item><title>  {title}  </title><link>https://club.example.org/alerts/post-{post}/</link>"
        f"<dc:creator><![CDATA[A. Volunteer]]></dc:creator><pubDate>{when}</pubDate>"
        f"<category>Trail Alerts</category><category>Section 4</category>"
        f'<guid isPermaLink="false">https://club.example.org/?post_type=alerts&amp;p={post}</guid>'
        "<description><![CDATA[<p>The footbridge washed out; ford with care.</p>]]></description>"
        "<content:encoded><![CDATA[<p>The footbridge washed out; ford with care.</p>]]></content:encoded></item>"
    )


def closures_feed(**options):
    return feed_notices("club_alerts_feed", club="testclub", type="closures", **options)


# --- FeedNotices -------------------------------------------------------------


def test_an_rss_item_lands_its_id_title_link_date_and_categories_and_no_prose_or_person(registry, requests_mock):
    requests_mock.get(FEED_URL, content=rss(rss_item(1122), rss_item(8019, "Reroute at the gap")))
    proofs: dict[str, int] = {}

    rows = list(closures_feed().rows(proofs))

    assert proofs == {"raw_testclub__club_alerts_feed": 2}, "the item count in the same response is the proof"
    assert set(rows[0]) == set(FEED_COLUMNS)
    assert rows[0]["item_id"] == "https://club.example.org/?post_type=alerts&p=1122"
    assert rows[0]["item_id_from"] == "guid"
    assert rows[0]["title"] == "Bridge out at Mile 12", "whitespace around a title is folded, as BLM's carry it"
    assert rows[0]["published"] == "Sun, 01 Mar 2026 13:52:08 +0000", "the date as the feed states it"
    assert rows[0]["updated"] is None, "RSS 2.0 states no updated date, and none is made up"
    assert rows[0]["categories"] == ["Trail Alerts", "Section 4"]
    assert rows[0]["listing"] == WINDOW
    assert [row["_row"] for row in rows] == [0, 1]
    landed_text = json.dumps(rows)
    assert "A. Volunteer" not in landed_text, "dc:creator names a person and never lands"
    assert "footbridge" not in landed_text, "description and content:encoded are prose and never land (decision 55)"
    assert rows[0]["item_sha256"] != rows[1]["item_sha256"]
    assert all(r.headers["User-Agent"] == USER_AGENT for r in requests_mock.request_history)


def test_an_atom_entry_lands_its_published_and_updated_dates_and_never_its_author(registry, requests_mock):
    atom = b"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"><title type="text">Section Updates</title>
    <updated>2026-10-03T14:37:50Z</updated>
    <entry><title>Section 1 - Gap to Ridge</title>
      <link rel="alternate" type="text/html" href="https://trail.example.org/section-updates/1-section-1"/>
      <published>2012-05-02T22:12:54Z</published><updated>2026-07-01T09:00:00Z</updated>
      <id>https://trail.example.org/section-updates/1-section-1</id>
      <author><name>Webmaster</name><email>webmaster@trail.example.org</email></author>
      <category term="Section Updates"/>
      <summary type="html">Blazes obscured near the old route.</summary></entry>
    </feed>"""
    requests_mock.get(ATOM_URL, content=atom)

    proofs: dict[str, int] = {}
    (row,) = list(feed_notices("section_updates", club="testclub", type="warnings").rows(proofs))

    assert proofs == {"raw_testclub__section_updates": 1}
    assert row["feed_format"] == "atom" and row["item_id_from"] == "id"
    assert row["link"] == "https://trail.example.org/section-updates/1-section-1"
    assert (row["published"], row["updated"]) == ("2012-05-02T22:12:54Z", "2026-07-01T09:00:00Z")
    assert row["categories"] == ["Section Updates"]
    assert "webmaster@" not in json.dumps(row) and "Blazes" not in json.dumps(row)


def test_an_empty_feed_proves_its_own_zero_and_a_closures_leg_loads_it(registry, store, requests_mock):
    requests_mock.get(FEED_URL, content=rss())

    report = leg(store, closures_feed())

    assert report.outcome == "loaded" and not report.isolated
    assert report.proofs == {"raw_testclub__club_alerts_feed": 0}
    assert landed(store, "raw_testclub__club_alerts_feed") == []


def test_a_page_answered_where_a_feed_was_is_never_read_as_an_empty_feed(registry, requests_mock):
    requests_mock.get(FEED_URL, text="<!DOCTYPE html><html><body>Page not found</body></html>")

    with pytest.raises(Exception, match="mismatched tag|not RSS 2.0 or Atom|not well-formed"):
        list(closures_feed().rows({}))
    assert closures_feed().change_check(None) == (Freshness.UNKNOWN, None)


def test_an_item_with_no_guid_id_or_link_cannot_be_keyed_and_refuses_the_read(registry, requests_mock):
    requests_mock.get(FEED_URL, content=rss("<item><title>Untitled notice</title></item>"))

    with pytest.raises(ValueError, match="no guid, id or link"):
        list(closures_feed().rows({}))


def test_a_304_to_a_trusted_feeds_own_etag_is_fresh_never_reaches_dlt_and_keeps_its_rows(registry, store, requests_mock):
    def answer(request, context):
        if request.headers.get("If-None-Match") == '"1790988271"':
            context.status_code = 304
            return b""
        context.headers["ETag"] = '"1790988271"'
        context.headers["Last-Modified"] = "Sat, 03 Oct 2026 00:44:31 GMT"
        return rss(rss_item(418421, "Area closed for construction"))

    requests_mock.get(BLM_FEED_URL, content=answer)
    resource = feed_notices("agency_press", trust_validators=True, club="testclub", type="closures")
    first = leg(store, resource)
    before = landed(store, "raw_testclub__agency_press")
    requests_mock.reset_mock()

    second = leg(store, resource)

    assert first.verdicts["raw_testclub__agency_press"] == "stale"
    assert second.verdicts["raw_testclub__agency_press"] == "fresh"
    assert second.load_id is None, "a FRESH resource is left out of the run, so nothing was extracted or loaded"
    (asked,) = requests_mock.request_history
    assert asked.headers["If-None-Match"] == '"1790988271"', "one conditional request, and the 304 answered it"
    assert landed(store, "raw_testclub__agency_press") == before, "the rows and their load id stand"


def test_an_untrusted_feed_sends_no_condition_and_is_fresh_only_while_its_items_hash_the_same(registry, requests_mock):
    """WordPress's feed validators are site-wide (GATC, CFPA, inventory 2026-10-03), so they are never sent or kept."""
    feed = {"body": rss(rss_item(1), rss_item(2))}
    requests_mock.get(FEED_URL, content=lambda request, context: feed["body"], headers={"ETag": 'W/"site-wide"'})

    verdict, marker = closures_feed().change_check(None)
    assert verdict is Freshness.STALE and marker["rows"] == "2" and "etag" not in marker
    assert closures_feed().change_check(marker) == (Freshness.FRESH, marker)
    feed["body"] = rss(rss_item(1), rss_item(2, "Bridge out at Mile 12, now reopened"))
    assert closures_feed().change_check(marker)[0] is Freshness.STALE, "an edited title moves the marker"
    feed["body"] = rss(rss_item(1))
    assert closures_feed().change_check(marker)[0] is Freshness.STALE, "an item gone from the window moves it too"
    assert not any("If-None-Match" in r.headers for r in requests_mock.request_history)


def test_the_check_and_the_read_of_one_run_ask_the_feed_once(registry, requests_mock):
    requests_mock.get(FEED_URL, content=rss(rss_item(1)))
    resource = closures_feed()

    verdict, _ = resource.change_check(None)
    rows = list(resource.rows({}))

    assert verdict is Freshness.STALE and len(rows) == 1
    assert requests_mock.call_count == 1


def test_a_walled_feed_is_unknown_its_read_asks_no_second_time_and_its_last_rows_stand(registry, store, requests_mock):
    requests_mock.get(FEED_URL, content=rss(rss_item(1)))
    leg(store, closures_feed())
    requests_mock.get(FEED_URL, status_code=403, text="Your access to this page has been blocked.")
    requests_mock.reset_mock()

    report = leg(store, closures_feed())

    assert report.verdicts["raw_testclub__club_alerts_feed"] == "unknown"
    assert "HTTP 403" in report.isolated["raw_testclub__club_alerts_feed"]
    assert requests_mock.call_count == 1, "the read raised what the check met, without asking the host again"
    assert [row["item_id"] for row in landed(store, "raw_testclub__club_alerts_feed")] == [
        "https://club.example.org/?post_type=alerts&p=1"
    ], "never zero: the last committed rows stand"


# --- PageNotice --------------------------------------------------------------

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Trail Conditions - A Trail Club</title>
<script type="application/ld+json">{"@graph": [{"@type": "WebSite", "dateModified": "2020-01-01T00:00:00Z"},
{"@type": "WebPage", "dateModified": "2026-08-17T21:09:14+00:00"}]}</script>
<script>var nonce = "%(nonce)s";</script></head>
<body class="render-%(nonce)s"><nav>Home | About | Donate</nav>
<main><h1>Current Trail Conditions</h1><p><strong>Last Updated: %(stated)s</strong></p>
<p>%(notice)s</p><h2>Segment A</h2><p>Last Updated: 6/24/26</p></main>
<footer>This page last updated: 2026-09-30 05:44:51</footer></body></html>"""


def page(stated="August 27, 2026", notice="The ridge trail is closed for a reroute.", nonce="a1") -> str:
    return PAGE % {"stated": stated, "notice": notice, "nonce": nonce}


def conditions(**options):
    return page_notice("club_conditions", club="testclub", type="closures", **options)


def test_a_page_is_one_notice_with_its_title_its_own_stated_date_and_a_hash_never_its_text(registry, requests_mock):
    requests_mock.get(PAGE_URL, text=page(), headers={"Content-Type": "text/html; charset=UTF-8"})
    proofs: dict[str, int] = {}

    (row,) = list(conditions().rows(proofs))

    assert proofs == {"raw_testclub__club_conditions": 1}
    assert set(row) == set(PAGE_COLUMNS)
    assert row["url"] == PAGE_URL and row["title"] == "Current Trail Conditions", "the region's <h1>, not <title>"
    assert (row["date"], row["date_text"], row["date_source"]) == ("2026-08-27", "August 27, 2026", "page_text")
    assert row["region"] == "main" and row["format"] == "html"
    assert "ridge trail" not in json.dumps(row), "the page's wording never lands (decision 55)"
    assert row["region_chars"] > 0 and len(row["region_sha256"]) == 64


def test_the_newest_stated_date_wins_and_a_footer_stamp_is_not_the_pages(registry, requests_mock):
    requests_mock.get(PAGE_URL, text=page(stated="6/1/26"))

    (row,) = list(conditions().rows({}))

    assert row["date"] == "2026-06-24", "the newest the region states"


def test_a_footer_stamp_is_the_sites_and_never_dates_a_page_read_whole(registry, requests_mock):
    """amc-wma.org's 'This page last updated' stamp was identical on two of its pages (inventory, 2026-10-03)."""
    whole = (
        "<html><head><title>Parking Areas</title></head><body><h1>Parking Areas</h1><p>Closed in winter.</p>"
        "<footer>This page last updated: 2026-09-30 05:44:51</footer></body></html>"
    )
    requests_mock.get(PAGE_URL, text=whole)

    (row,) = list(conditions().rows({}))

    assert (row["region"], row["date"]) == ("body", None)


def test_a_page_with_no_stated_date_takes_its_json_ld_date_and_says_so(registry, requests_mock):
    requests_mock.get(PAGE_URL, text=page(stated="soon").replace("Last Updated: 6/24/26", ""))

    (row,) = list(conditions().rows({}))

    assert (row["date"], row["date_source"]) == ("2026-08-17", "json_ld"), "the WebPage node's dateModified"
    assert row["date_text"] == "2026-08-17T21:09:14+00:00"


def test_a_page_with_no_date_at_all_lands_none_and_a_request_time_last_modified_does_not_date_it(registry, requests_mock):
    bare = "<html><head><title>Alerts</title></head><body><main><h1>Alerts</h1><p>Wear orange in season.</p></main></body></html>"
    requests_mock.get(PAGE_URL, text=bare, headers={"Last-Modified": "Sat, 03 Oct 2026 14:30:21 GMT"})

    (row,) = list(conditions().rows({}))
    _notices._ANSWERS.clear()
    (trusted,) = list(conditions(trust_validators=True).rows({}))

    assert (row["date"], row["date_text"], row["date_source"]) == (None, None, None), "absent means unknown"
    assert (trusted["date"], trusted["date_source"]) == ("2026-10-03", "last_modified"), "only where measured as the page's"


def test_a_per_render_token_leaves_the_hash_and_a_changed_notice_moves_it(registry, requests_mock):
    body = {"text": page(nonce="a1")}
    requests_mock.get(PAGE_URL, text=lambda request, context: body["text"])

    verdict, marker = conditions().change_check(None)
    body["text"] = page(nonce="zz9")
    assert conditions().change_check(marker) == (Freshness.FRESH, marker), "a script nonce and a class token are not the notice"
    body["text"] = page(notice="The ridge trail has reopened.")
    assert conditions().change_check(marker)[0] is Freshness.STALE
    assert verdict is Freshness.STALE


def test_a_304_to_a_trusted_pages_own_last_modified_is_fresh_and_never_reaches_dlt(registry, store, requests_mock):
    def answer(request, context):
        if request.headers.get("If-Modified-Since") == "Tue, 25 Aug 2026 19:18:38 GMT":
            context.status_code = 304
            return ""
        context.headers["Last-Modified"] = "Tue, 25 Aug 2026 19:18:38 GMT"
        return page()

    requests_mock.get(PAGE_URL, text=answer)
    leg(store, conditions(trust_validators=True))
    requests_mock.reset_mock()

    report = leg(store, conditions(trust_validators=True))

    assert report.verdicts["raw_testclub__club_conditions"] == "fresh" and report.load_id is None
    (asked,) = requests_mock.request_history
    assert asked.headers["If-Modified-Since"] == "Tue, 25 Aug 2026 19:18:38 GMT", "one conditional request, answered 304"
    assert [row["title"] for row in landed(store, "raw_testclub__club_conditions")] == ["Current Trail Conditions"]


@pytest.mark.parametrize(
    "answer",
    [
        {"status_code": 403, "headers": {"cf-mitigated": "challenge"}, "text": "<title>Just a moment...</title>"},
        {"status_code": 429, "headers": {"x-vercel-mitigated": "challenge"}, "text": "<title>Vercel Security Checkpoint</title>"},
        {"status_code": 202, "headers": {"sg-captcha": "challenge"}, "text": '<meta http-equiv="refresh" content="0">'},
        {"status_code": 200, "text": "<html><head><title>Just a moment...</title></head><body>Checking</body></html>"},
        {"status_code": 200, "headers": {"cf-mitigated": "challenge"}, "text": page()},
    ],
    ids=["cloudflare-403", "vercel-429", "siteground-202", "challenge-page-200", "challenge-header-200"],
)
def test_a_walled_page_is_unknown_and_its_last_row_stands(registry, store, requests_mock, answer):
    requests_mock.get(PAGE_URL, text=page())
    leg(store, conditions())
    requests_mock.get(PAGE_URL, **answer)

    report = leg(store, conditions())

    assert report.verdicts["raw_testclub__club_conditions"] == "unknown"
    assert "raw_testclub__club_conditions" in report.isolated
    assert [row["title"] for row in landed(store, "raw_testclub__club_conditions")] == ["Current Trail Conditions"]


def test_a_429_is_not_retried_because_the_hourly_lane_is_the_retry(registry, requests_mock):
    requests_mock.get(PAGE_URL, status_code=429)

    assert conditions().change_check(None) == (Freshness.UNKNOWN, None)
    assert requests_mock.call_count == 1


def test_a_gone_page_refuses_rather_than_reading_its_notice_as_lifted(registry, requests_mock):
    requests_mock.get(PAGE_URL, status_code=404)

    with pytest.raises(NoticeUnreadable, match="HTTP 404"):
        list(conditions().rows({}))


def test_a_page_that_redirects_to_another_host_is_unknown(registry, requests_mock):
    requests_mock.get(PAGE_URL, status_code=301, headers={"Location": "https://another-club.example.net/"})
    requests_mock.get("https://another-club.example.net/", text=page())

    with pytest.raises(NoticeUnreadable, match="another host"):
        list(conditions().rows({}))


def test_a_redirect_to_the_same_site_under_www_is_followed(registry, requests_mock):
    requests_mock.get(PAGE_URL, status_code=301, headers={"Location": "https://www.club.example.org/trail-conditions/"})
    requests_mock.get("https://www.club.example.org/trail-conditions/", text=page())

    assert [row["title"] for row in conditions().rows({})] == ["Current Trail Conditions"]


def test_a_page_whose_title_no_longer_names_the_notice_refuses(registry, requests_mock):
    requests_mock.get(PAGE_URL, text="<html><body><main><h1>Trail Maps</h1></main></body></html>")

    with pytest.raises(NoticeUnreadable, match="no longer names"):
        list(conditions(expect_title="Conditions").rows({}))


def test_a_named_region_is_what_is_read_and_a_page_that_lost_it_has_changed_shape(registry, requests_mock):
    requests_mock.get(
        PAGE_URL,
        text='<html><body><h1>Club Name</h1><div id="alert-block"><h1>Park Alerts</h1>Burn ban in effect</div></body></html>',
    )
    (row,) = list(conditions(region="#alert-block").rows({}))
    assert (row["region"], row["title"]) == ("#alert-block", "Park Alerts")

    requests_mock.get(PAGE_URL, text="<html><body><h1>Club Name</h1></body></html>")
    with pytest.raises(NoticeUnreadable, match="changed shape"):
        list(conditions(region="#alert-block").rows({}))


def test_a_fragment_with_no_title_of_its_own_carries_the_registry_rows_only_when_asked(registry, requests_mock):
    requests_mock.get(PAGE_URL, text='<ul class="alerts"><li><span>Fest moved to Oct 17</span></li></ul>')

    with pytest.raises(NoticeUnreadable, match="no <h1>, og:title or <title>"):
        list(conditions().rows({}))
    (row,) = list(conditions(registry_title=True).rows({}))
    assert (row["title"], row["region"]) == ("Trail Conditions", "document")


def test_a_wordpress_page_is_read_through_its_rest_route_with_no_query_string(registry, requests_mock):
    """foothillstrail.org's robots.txt disallows `/*?`, and its /wp-json/wp/v2/pages/25 was allowed (inventory)."""
    post = {
        "id": 25,
        "modified_gmt": "2025-04-13T13:22:46",
        "title": {"rendered": "Trail Conditions &#038; Closures"},
        "content": {"rendered": "<p>Trail Update 4/13: a tree down near the falls.</p>"},
        "author": 1,
    }
    requests_mock.get("https://foothillstrail.org/wp-json/wp/v2/pages/25", json=post)

    (row,) = list(page_notice("wpstaq_conditions", wp_page=25, club="testclub", type="closures").rows({}))

    (asked,) = requests_mock.request_history
    assert asked.url == "https://foothillstrail.org/wp-json/wp/v2/pages/25", "no query string on this host"
    assert row["title"] == "Trail Conditions & Closures" and row["url"] == WP_PAGE_URL
    assert (row["date"], row["date_source"]) == ("2025-04-13", "wp_modified"), "'4/13' has no year, so it is not read"
    assert row["format"] == "wp_rest" and "tree down" not in json.dumps(row)


def test_a_query_url_is_refused_at_import_on_a_host_whose_robots_txt_disallows_them(registry):
    with pytest.raises(ValueError, match="disallows every URL with a query string"):
        page_notice("wpstaq_query")
    with pytest.raises(ValueError, match="every WordPress list request carries one"):
        wordpress_posts("wpstaq_category")


def test_a_pdf_notice_carries_the_registry_title_its_own_metadata_date_and_the_bytes_hash(registry, requests_mock, monkeypatch):
    monkeypatch.setattr(
        _notices,
        "read_pdf",
        lambda body: PdfFacts(texts=("Logging at MM 194-195",), created=("D:20260108120000-05'00'", "2026-01-08")),
    )
    requests_mock.get(
        PDF_URL,
        content=b"%PDF-1.7 hiker alert",
        headers={"Content-Type": "application/pdf", "ETag": '"6aab-1"', "Last-Modified": "Thu, 17 Sep 2026 01:53:43 GMT"},
    )

    (row,) = list(page_notice("hiker_alert_pdf", club="testclub", type="warnings").rows({}))

    assert row["title"] == "Hiker Alert: logging" and row["format"] == "pdf"
    assert (row["date"], row["date_source"]) == ("2026-01-08", "pdf_created"), "the document's date, never the server's"
    assert row["region_chars"] == len(b"%PDF-1.7 hiker alert")


def test_a_pdfs_metadata_dates_are_read_and_a_malformed_one_is_no_date():
    """Needs pypdf, which only requirements-extract.txt pins, so the pipeline suite's environment skips it."""
    pypdf = pytest.importorskip("pypdf")
    from io import BytesIO

    def pdf(metadata: dict) -> bytes:
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_metadata(metadata)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    facts = _notices.read_pdf(pdf({"/CreationDate": "D:20260108120000-05'00'", "/ModDate": "D:20260917015343Z"}))
    assert (facts.modified, facts.created) == (
        ("D:20260917015343Z", "2026-09-17"),
        ("D:20260108120000-05'00'", "2026-01-08"),
    )
    assert _notices.read_pdf(pdf({"/CreationDate": "not a date"})).created is None


# --- The stated date ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Updated August 17, 2026", ("August 17, 2026", "2026-08-17")),
        ("Last Updated: August 27, 2026", ("August 27, 2026", "2026-08-27")),
        ("This page was updated on September 28, 2026.", ("September 28, 2026", "2026-09-28")),
        ("Knobstone Trail conditions Update: July 21, 2026", ("July 21, 2026", "2026-07-21")),
        ("Update 7/30/2025", ("7/30/2025", "2025-07-30")),
        ("Updated 9/4/26 and roads Updated 5/29/26", ("9/4/26", "2026-09-04")),
        ("Updated Sep. 24, 2026, 12:22 pm", ("Sep. 24, 2026", "2026-09-24")),
        ("Updated Sept 2, 2026", ("Sept 2, 2026", "2026-09-02")),
        ("Trail Update 4/13", None),
        ("Updated 9/31/26", None),
        ("Page updated", None),
        ("Updated December 1, 2099", None),
    ],
)
def test_a_page_states_its_own_date_in_the_words_the_inventory_measured(text, expected):
    assert page_stated_date(text) == expected


def test_a_page_with_its_own_wording_states_its_date_through_a_pattern_around_date():
    import re

    pattern = re.compile(r"New this week \(" + DATE + r"\)", re.IGNORECASE)
    assert page_stated_date("Backcountry information. New this week (10/1/2026)", pattern) == ("10/1/2026", "2026-10-01")


# --- Politeness ----------------------------------------------------------------


def test_every_request_to_one_host_waits_out_its_crawl_delay_end_to_start(monkeypatch, requests_mock, quiet_gates_and_answers):
    clock = {"now": 100.0}
    monkeypatch.setattr(_notices, "_now", lambda: clock["now"])
    requests_mock.get("https://club.example.org/a", text="a")
    requests_mock.get("https://www.club.example.org/b", text="b")
    requests_mock.get("https://elsewhere.example.net/c", text="c")
    http = polite(_kinds.session(), 10)

    http.get("https://club.example.org/a")
    clock["now"] += 3
    http.get("https://www.club.example.org/b")
    http.get("https://elsewhere.example.net/c")

    assert quiet_gates_and_answers == [7.0], "the same site under www waits the rest of its 10 s; another host does not"


# --- WordpressPosts' options -----------------------------------------------------


def test_wordpress_posts_read_several_categories_as_one_table(registry, requests_mock):
    requests_mock.get(
        WP + "/categories",
        json=[{"id": 37, "slug": "closures"}, {"id": 40, "slug": "closures-north"}],
    )
    requests_mock.get(
        WP + "/posts", json=[{"id": 1, "slug": "a", "modified_gmt": "2026-07-28T19:11:50"}], headers={"X-WP-Total": "1"}
    )
    resource = wordpress_posts("club_closures", category_slugs=["closures", "closures-north"], club="testclub", type="closures")

    rows = list(resource.rows({}))

    lookup, posts = requests_mock.request_history
    assert lookup.qs["slug"] == ["closures,closures-north"]
    assert posts.qs["categories"] == ["37,40"] and [row["id"] for row in rows] == [1]


def test_a_category_slug_the_site_does_not_resolve_refuses_rather_than_narrowing(registry, requests_mock):
    requests_mock.get(WP + "/categories", json=[{"id": 37, "slug": "closures"}])
    resource = wordpress_posts("club_closures", category_slugs=("closures", "closures-north"), club="testclub", type="closures")

    with pytest.raises(RuntimeError, match="'closures-north' resolves to 0 ids"):
        list(resource.rows({}))


def test_wordpress_posts_read_a_custom_post_type_whole_and_drop_its_author_blocks(registry, requests_mock):
    alert = {
        "id": 9,
        "slug": "fire-towers-closed",
        "modified_gmt": "2026-10-01T12:00:00",
        "title": {"rendered": "Fire Towers Closed"},
        "alert-category": [3],
        "uagb_author_info": {"display_name": "A. Staffer"},
        "spectra_custom_meta": {"_edit_lock": ["1790000000:2"]},
    }
    requests_mock.get(WP + "/alert", json=[alert], headers={"X-WP-Total": "1"})
    resource = wordpress_posts("club_alert_type", post_type="alert", club="testclub", type="closures")
    proofs: dict[str, int] = {}

    (row,) = list(resource.rows(proofs))

    assert "categories" not in requests_mock.request_history[0].qs, "a custom post type sits in no category"
    assert proofs == {"raw_testclub__club_alert_type": 1} and row["alert-category"] == [3]
    assert "A. Staffer" not in json.dumps(row) and "spectra_custom_meta" not in row
    with pytest.raises(ValueError, match="takes no category_slugs"):
        wordpress_posts("club_alert_type", post_type="alert", category_slugs=("x",))


def test_wordpress_posts_keep_the_hosts_crawl_delay_between_their_requests(registry, requests_mock, quiet_gates_and_answers):
    requests_mock.get(WP + "/categories", json=[{"id": 6, "slug": "closures"}])
    requests_mock.get(WP + "/posts", json=[], headers={"X-WP-Total": "0"})

    list(wordpress_posts("club_closures", crawl_delay=10, club="testclub", type="closures").rows({}))
    assert len(quiet_gates_and_answers) == 1 and 9 < quiet_gates_and_answers[0] <= 10
    assert WordpressPosts(key="club_closures").crawl_delay == 0, "NYNJTC's asks none, and sends as it always has"
