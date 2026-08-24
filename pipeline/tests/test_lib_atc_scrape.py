"""Reading ATC's HTML into facts, and refusing when it stops looking familiar.

Their HTML is not an API (#463), so the interesting cases here are all about
what happens when the page is not what this build expects. The rule the module
follows is that a half-understood page produces nothing: a safety notice built
out of the half that still parsed after a theme change is the confident wrong
answer features/ATC_TRAIL_UPDATES.md is written against.

Two of the tests below are regressions for bugs that actually happened while
this was being built, and both were silent rather than loud - see
`test_the_nav_is_cut_at_the_last_privacy_policy_not_the_first` and
`test_the_session_replaces_the_user_agent_rather_than_defaulting_it`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from lib.atc_scrape import (
    CACHE_TTL,
    USER_AGENT,
    article_text,
    atc_session,
    listing_slugs,
    listing_url,
    parse_update,
    plan_fetches,
)

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def page(
    title: str = "Central VA: War Spur Bridge Closed",
    chip: str = "VA | Closure",
    modified: str = '"dateModified":"2026-08-19T16:22:50-04:00"',
    body: str = "The War Spur Branch Bridge is closed (NOBO mile 670.2).",
) -> str:
    """One update page, shaped like ATC's real ones.

    The nav ending in "Privacy Policy" and the newsletter block opening with
    "Stay Connected" are both real and both load-bearing, so the fixture keeps
    them rather than handing the parser a clean document it will never meet.
    """
    return f"""
    <html><head><title>{title} - Appalachian Trail Conservancy</title>
    <script type="application/ld+json">{{{modified},"datePublished":"2026-08-19T16:22:50-04:00"}}</script>
    </head><body><main>
      <nav><a>Hike the Trail</a><a>Maine</a><a>Virginia</a></nav>
      <a>Terms, Conditions, &amp; Policies</a><a>Privacy Policy</a>
      <h1>{title}</h1><span>{chip}</span><span>4 DAYS AGO</span>
      <p>{body}</p>
      <h2>Stay Connected</h2><form><input name="email"></form>
    </main></body></html>
    """


def test_a_normal_page_becomes_facts():
    parsed = parse_update(page(), "central-va-war-spur-bridge-closed")

    assert parsed is not None
    assert parsed.title == "Central VA: War Spur Bridge Closed"
    assert parsed.category == "Closure"
    assert parsed.states == ["VA"]
    assert parsed.date_modified == "2026-08-19T16:22:50-04:00"
    assert [(m.start, m.end) for m in parsed.miles] == [(670.2, None)]
    assert parsed.source_url.endswith("/central-va-war-spur-bridge-closed/")


def test_several_states_are_all_kept():
    parsed = parse_update(page(chip="NC, TN | Animal"), "bear")

    assert parsed is not None and parsed.states == ["NC", "TN"] and parsed.category == "Animal"


def test_a_page_with_no_modified_date_is_refused():
    """Every one of the 89 updates live on 2026-08-24 carried `dateModified`.
    A page without one is a page whose shape has changed, and the age of a
    notice is the fact this whole feature turns on."""
    assert parse_update(page(modified='"somethingElse":"x"'), "slug") is None


def test_a_page_with_no_title_is_refused():
    assert parse_update("<html><body><main>no head at all</main></body></html>", "slug") is None


def test_the_thousands_separator_survives_the_parse():
    """`NOBO mile 1,503.6` read without the comma is mile 1 - a Connecticut
    shelter drawn in Georgia. It parses, it looks plausible, and it is 1,502
    miles wrong; spike_atc_updates.py recorded it as a near-miss before this
    module existed."""
    parsed = parse_update(page(body="Limestone Spring Shelter (NOBO mile 1,503.6) is closed."), "s")

    assert parsed is not None and parsed.miles[0].start == 1503.6


def test_a_range_keeps_both_ends():
    parsed = parse_update(page(body="Closed from NOBO mile 476.6 to 485.8 for construction."), "s")

    assert parsed is not None and (parsed.miles[0].start, parsed.miles[0].end) == (476.6, 485.8)


def test_the_nav_is_cut_at_the_last_privacy_policy_not_the_first():
    """A regression, and it was silent.

    "Privacy Policy" appears twice on a real page - once in the head's title
    text and once at the end of the navigation menu. Cutting at the FIRST
    occurrence leaves the whole menu in front of the prose, and that menu is a
    list of state names: `Maine`, `Virginia`, and so on. The chip pattern then
    matches against navigation instead of the update's own category, which
    produces a row that is wrong rather than absent.
    """
    text = article_text(page())

    assert text.startswith("Central VA: War Spur Bridge Closed")
    assert "Hike the Trail" not in text


def test_the_newsletter_block_is_not_part_of_the_update():
    assert "Stay Connected" not in article_text(page())


def test_listing_slugs_are_read_in_the_order_shown():
    markup = "".join(
        f'<a href="https://appalachiantrail.org/trail-updates/{slug}/" aria-label="View x update">'
        for slug in ("first", "second", "first")
    )

    assert listing_slugs(markup) == ["first", "second"]


def test_the_listing_pager_spells_page_one_without_a_number():
    assert listing_url(1).endswith("/trail-updates/")
    assert listing_url(3).endswith("/trail-updates/page/3/")


def test_a_slug_with_no_cached_copy_is_fetched():
    assert plan_fetches(["new"], {}, NOW) == ["new"]


def test_a_freshly_cached_slug_is_not_fetched_again():
    """What keeps an hourly job from costing 99 requests an hour at somebody
    else's expense."""
    cache = {"seen": {"fetched_at": (NOW - timedelta(hours=1)).isoformat()}}

    assert plan_fetches(["seen"], cache, NOW) == []


def test_a_cached_copy_past_its_life_is_fetched_again():
    """ATC's listing cannot say that an old notice was edited - it sorts by
    `datePublished`, so an edit never moves a row - which leaves time as the
    only trigger there is."""
    cache = {"seen": {"fetched_at": (NOW - CACHE_TTL - timedelta(minutes=1)).isoformat()}}

    assert plan_fetches(["seen"], cache, NOW) == ["seen"]


def test_an_unreadable_cache_stamp_is_fetched_rather_than_trusted():
    assert plan_fetches(["seen"], {"seen": {"fetched_at": "not a date"}}, NOW) == ["seen"]


def test_the_session_replaces_the_user_agent_rather_than_defaulting_it():
    """A regression, and it cost a 403 on the first live run.

    ATC's host refuses the literal `python-requests/*` User-Agent and answers
    200 to anything else (measured 2026-08-24). A fresh `requests.Session`
    already carries that header, so setting it only-if-absent finds one there,
    leaves it, and gets refused - which looks exactly like ATC blocking the
    project rather than like a one-line bug.
    """
    session = atc_session()

    assert session.headers["User-Agent"] == USER_AGENT
    assert "python-requests" not in session.headers["User-Agent"]


def test_a_caller_supplied_session_is_relabelled_too():
    session = requests.Session()

    assert atc_session(session).headers["User-Agent"] == USER_AGENT
