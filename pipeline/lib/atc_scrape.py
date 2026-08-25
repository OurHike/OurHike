"""Reading ATC's Trail Updates off their website, because there is no API.

features/ATC_TRAIL_UPDATES.md is the design and #963 is the issue. This module
owns one job - **turn ATC's HTML into facts** - and deliberately owns nothing
about whether those facts are safe to publish. That question is
`lib/atc_updates.py`'s, and keeping the two apart is what lets the gate be
tested without a network and the parse be tested without a policy.

THEIR HTML IS NOT AN API, which #463 says and this module has to live with. A
theme change breaks the parse. So every extractor here either finds what it
is looking for or returns None, and `parse_update` refuses to build a row out
of a page it only half understood - a half-parsed safety notice is the
confident wrong answer this whole feature is fenced against.

WHAT IS READ FROM WHERE, and why not from the obvious place:

    the slug set      the ten listing pages
    dateModified      JSON-LD on each update's own page
    category, states  the chip under the title on each update's own page
    the mile          ATC's prose, via MILE_REFERENCE

`dateModified` is the one worth explaining. ATC's listing sorts by
`datePublished` DESCENDING - verified 2026-08-24 across all 89 updates then
live, which came back in strict published order and NOT in modified order. So
a notice they re-edit every season never moves up the list: the three yearly
bear warnings sat on page NINE, 1,189 to 1,496 days down by the listing's own
clock, each edited 116 days earlier. Listing position says when ATC first
posted a thing and nothing whatever about whether it is still true, so nothing
here reads recency off the listing.

BEING POLITE TO SOMEBODY ELSE'S SERVER IS PART OF THE DESIGN. There were 89
updates live on 2026-08-24 across ten pages. Fetching every page and every
update, hourly, is 99 requests an hour and 2,376 a day at somebody else's
expense, for data that changes a few times a month. So `plan_fetches` fetches
the ten listing pages and then asks for an update's own page only when it is
NEW or when the copy on disk has gone stale, which settles at roughly ten
requests an hour plus one refresh per update per day.
"""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

from lib.http_retry import request_with_retry

LISTING_URL = "https://appalachiantrail.org/trail-updates/"

#: WHO WE SAY WE ARE, and this is load-bearing rather than courtesy. ATC's
#: host refuses the literal `python-requests/*` User-Agent with 403 and
#: answers 200 to anything else - measured 2026-08-24, the same URL, the same
#: second:
#:
#:     python-requests/2.32.3   403
#:     curl/8.5.0               200
#:     (this string)            200
#:
#: So a fetcher that does not set one gets nothing, and every request here
#: goes through `atc_session()` for that reason. It names the project and
#: links to it rather than impersonating a browser: the block is on the
#: default, not on robots, and an operator who wants to throttle or contact us
#: should be able to see who this is from one line of their log.
USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"

#: How long a cached copy of one update's page is trusted before it is asked
#: for again. A day, so that an edit ATC makes to an old notice is picked up
#: within one, rather than never - the listing cannot tell us an edit happened
#: (see the `dateModified` note above), so time is the only trigger there is.
CACHE_TTL = timedelta(hours=24)

#: A hard ceiling on how far the pager will walk, so a listing that starts
#: linking to itself cannot spin forever. Ten pages held all 89 updates on
#: 2026-08-24; twice that is room to grow into and still a stop.
MAX_LISTING_PAGES = 20

# How ATC writes a location, taken from real pages rather than imagined. The
# thousands comma is the detail that matters: a pattern without it truncates
# `NOBO mile 1,503.6` to mile 1, which is a Connecticut shelter reported as a
# spot in Georgia. It parses, it looks plausible, and it is 1,502 miles wrong.
_MILE_NUMBER = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?"
MILE_REFERENCE = re.compile(
    rf"(?P<direction>NOBO|SOBO)\s+miles?\s+(?P<start>{_MILE_NUMBER})"
    rf"(?:\s*(?:to|through|-|–|—)\s*(?P<end>{_MILE_NUMBER}))?",
    re.IGNORECASE,
)

_SLUG_IN_LISTING = re.compile(
    r'href="https://appalachiantrail\.org/trail-updates/([a-z0-9-]+)/"\s+aria-label="View',
)
_JSON_LD_DATE = r'"{key}"\s*:\s*"([^"]+)"'
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_DROPPED_ELEMENTS = re.compile(r"<(script|style|nav|footer|header|form)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
# The chip under the headline: "VA | Detour", "NC, TN | Animal".
_CHIP = re.compile(r"^\s*((?:[A-Z]{2})(?:,\s*[A-Z]{2})*)\s*\|\s*([A-Za-z][A-Za-z ]*?)\s*(?:\*|\d|$)")


def atc_session(session: requests.Session | None = None) -> requests.Session:
    """A session that identifies itself, because the default one is refused.

    Assignment rather than `setdefault`: a fresh `requests.Session` already
    carries `User-Agent: python-requests/...`, so setting it only-if-absent
    finds one present, leaves it, and gets the 403 this function exists to
    avoid. That is not hypothetical - it is what the first version of this
    did.
    """
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def update_url(slug: str) -> str:
    return f"{LISTING_URL}{slug}/"


def listing_url(page: int) -> str:
    return LISTING_URL if page == 1 else f"{LISTING_URL}page/{page}/"


@dataclass
class MileReference:
    """One "NOBO mile X to Y" as ATC wrote it, and as numbers.

    `end is None` means ATC named a point rather than a range, and the
    distinction is kept rather than collapsed: a shelter at a mile and a
    nine-mile closure are different things to draw.
    """

    direction: str
    start: float
    end: float | None
    raw: str


@dataclass
class ParsedUpdate:
    """One update, as facts. Says nothing about whether it may be published."""

    slug: str
    title: str
    category: str | None
    states: list[str] = field(default_factory=list)
    date_modified: str | None = None
    date_published: str | None = None
    miles: list[MileReference] = field(default_factory=list)
    text: str = ""

    @property
    def source_url(self) -> str:
        return update_url(self.slug)


def _number(raw: str | None) -> float | None:
    return None if raw is None else float(raw.replace(",", ""))


def strip_html(markup: str) -> str:
    """Tags out, entities in, whitespace flattened.

    Deliberately not an HTML parser: the only thing this has to get right is
    that words either side of a tag do not run together into a token the mile
    pattern could misread.
    """
    return _WHITESPACE.sub(" ", html_module.unescape(_TAG.sub(" ", markup))).strip()


def article_text(markup: str) -> str:
    """The update's own prose, with the site chrome taken off both ends.

    The leading nav ends at the privacy-policy link and the trailing
    newsletter form starts at "Stay Connected" - both measured against the
    real pages on 2026-08-24. Cutting at the LAST privacy-policy occurrence
    matters: the phrase also appears in the document title, and cutting at the
    first one leaves the whole navigation menu in front of the prose, where
    its state names look enough like a chip to be misread as one.
    """
    body = re.search(r"<main.*?</main>", markup, re.DOTALL)
    inner = body.group(0) if body else markup
    text = strip_html(_DROPPED_ELEMENTS.sub(" ", inner))
    cut = text.rfind("Privacy Policy")
    if cut >= 0:
        text = text[cut + len("Privacy Policy") :].strip()
    for tail in ("Stay Connected", "Manage Consent"):
        end = text.find(tail)
        if end > 0:
            text = text[:end].strip()
    return text


def listing_slugs(markup: str) -> list[str]:
    """The update slugs one listing page links to, in the order shown."""
    seen: dict[str, None] = {}
    for slug in _SLUG_IN_LISTING.findall(markup):
        seen.setdefault(slug, None)
    return list(seen)


def parse_update(markup: str, slug: str) -> ParsedUpdate | None:
    """One update page as facts, or None if the page was not understood.

    None rather than a partial row, because the caller's next move is to
    decide whether a hiker sees this: a row built out of the half of a page
    that still parsed after a theme change is exactly the confident wrong
    answer features/ATC_TRAIL_UPDATES.md is written against.
    """
    title_tag = re.search(r"<title>(.*?)</title>", markup, re.DOTALL)
    if not title_tag:
        return None
    title = html_module.unescape(title_tag.group(1))
    title = re.sub(r"\s*-\s*Appalachian Trail Conservancy\s*$", "", title).strip()
    if not title:
        return None

    modified = re.search(_JSON_LD_DATE.format(key="dateModified"), markup)
    published = re.search(_JSON_LD_DATE.format(key="datePublished"), markup)
    if not modified:
        # Every one of the 89 updates live on 2026-08-24 carried it. A page
        # without one is a page whose shape has changed.
        return None

    text = article_text(markup)
    chip = _CHIP.match(text[len(title) :].lstrip()) if text.startswith(title) else None

    return ParsedUpdate(
        slug=slug,
        title=title,
        category=chip.group(2).strip() if chip else None,
        states=[s.strip() for s in chip.group(1).split(",")] if chip else [],
        date_modified=modified.group(1),
        date_published=published.group(1) if published else None,
        miles=[
            MileReference(
                direction=m.group("direction").upper(),
                start=_number(m.group("start")),
                end=_number(m.group("end")),
                raw=m.group(0),
            )
            for m in MILE_REFERENCE.finditer(text)
        ],
        text=text,
    )


def fetch_listing_slugs(session: requests.Session | None = None) -> list[str]:
    """Every slug ATC currently lists, walking the pager to its end.

    Stops on the first page that adds nothing new, which is what the end of
    the pager looks like from here: page 11 answered 200 with no update
    anchors on it (measured 2026-08-24), so a 404 is not the signal.
    """
    session = atc_session(session)
    slugs: dict[str, None] = {}
    for page in range(1, MAX_LISTING_PAGES + 1):
        response = request_with_retry(listing_url(page), session=session, label=f"ATC trail updates page {page}")
        found = listing_slugs(response.text)
        fresh = [slug for slug in found if slug not in slugs]
        if not fresh:
            break
        for slug in fresh:
            slugs.setdefault(slug, None)
    return list(slugs)


def plan_fetches(slugs: list[str], cache: dict, now: datetime) -> list[str]:
    """Which update pages actually need asking for this run.

    A new slug always does. A cached one does when its copy is older than
    `CACHE_TTL`, because ATC's listing cannot tell us an edit happened and
    time is the only trigger available. Everything else is served from disk,
    which is what keeps an hourly job from costing 99 requests an hour.
    """
    due = []
    for slug in slugs:
        entry = cache.get(slug)
        fetched_at = (entry or {}).get("fetched_at")
        if not fetched_at:
            due.append(slug)
            continue
        try:
            stamped = datetime.fromisoformat(fetched_at)
        except ValueError:
            due.append(slug)
            continue
        if stamped.tzinfo is None:
            stamped = stamped.replace(tzinfo=timezone.utc)
        if now - stamped >= CACHE_TTL:
            due.append(slug)
    return due


def fetch_update(slug: str, session: requests.Session | None = None) -> ParsedUpdate | None:
    """One update page, fetched and parsed."""
    response = request_with_retry(update_url(slug), session=atc_session(session), label=f"ATC trail update {slug}")
    return parse_update(response.text, slug)
