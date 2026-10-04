"""Two generic notice readers for decision 53's phase B: FeedNotices (RSS 2.0 and Atom) and PageNotice (one notice a page).

pipeline/ELT.md, "Every club's closures and alerts (decision 53)", phase B, is
the design: every club's closures and alerts become a one-line resource over
a generic reader, one reader per format. These two are the RSS-or-Atom and
the HTML-page rows of that table, with the PDF row folded into PageNotice.
They live here rather than in extract/_kinds.py, which was 2,025 lines, and
_kinds.py imports them, so a club file writes `from extract._kinds import
page_notice` like any other builder. This module imports nothing from
_kinds.py at its top, because _kinds.py imports it: `_kinds()` below fetches
the registry and the named session when a reader runs, which is also what
lets fixture mode's swapped `_kinds.session` reach them.

Both readers keep the rules decision 53 set (ELT.md, "The rules this keeps"),
and decision 55 (the maintainer's poll, 2026-10-03): facts and a link,
never the club's paragraphs. A row carries a title, a date as the source
states it, the link, and a sha256 of what the source said, so a change is
detectable and no wording is copied. No description, no `content:encoded`,
no page text lands in any column, and no author: RSS `dc:creator` and
Atom `<author>` name staff (BLM's Utah feed, CFPA's and GATC's carry a
person's name; the Mid State Trail's Atom feed an e-mail address; read in
decision 53's inventory, 2026-10-03), so the readers name the fields they
keep and drop everything else.

THE INVENTORY these were designed from is decision 53's phase A, run
2026-10-03 against all 129 clubs, one request per URL under lib/user_agent.py's
agent, every robots.txt read first (kept in the session's scratchpad, never
in the repository). Where a docstring here says "the inventory" it means that
read, and the batch in brackets ([b1] to [b5]) is the worker that measured it.

Both readers are hourly when they feed closures or warnings (decision 28a),
and both are gentle the way decision 53 asks:

- ONE REQUEST A RUN. The change check's read is kept for the read that
  follows in the same run (`_remember()`), so a STALE source costs one
  request, not two, and a source the check could not read is not asked again
  by the read: it raises what the check met.
- EVERY HOST'S CRAWL-DELAY. `crawl_delay` is the robots.txt value the
  inventory read for the host; every request waits at least that long after
  the last one to that host ended, and at least DEFAULT_HOST_GAP_SECONDS
  where robots.txt asks for nothing (`polite()`).
- NEVER A QUERY STRING WHERE ROBOTS.TXT FORBIDS ONE (QUERY_DISALLOWED_HOSTS).
  Neither reader builds a query string at all: each asks exactly the URL the
  registry row holds, or, for a WordPress page read through the REST API,
  `/wp-json/wp/v2/pages/<id>` with none.
- A WALL IS UNKNOWN, NEVER ZERO. A 401, 403, 429 or 451, a challenge header
  or a challenge page's title raises NoticeUnreadable: the change check
  answers UNKNOWN, the read raises, and a conditions leg leaves the resource
  out with its last committed rows standing (extract/_run.py's read_each). A
  429 is not retried here, because the hourly lane is the retry.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlparse

import requests

from extract._contract import Resource
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry


def _kinds():
    """extract/_kinds.py, imported when a reader runs: it imports this module, so this one cannot import it first."""
    from extract import _kinds as kinds

    return kinds


def _canonical(marker: dict) -> str:
    return json.dumps(marker, sort_keys=True)


def _sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


# --- Access: query strings, walls, redirects --------------------------------

# Hosts whose robots.txt disallows every URL with a query string for every
# agent, `Disallow: /*?` under `User-agent: *`, each the WPStaq hosting
# default (read in the inventory, 2026-10-03): foothillstrail.org [b1], which
# also asks `Crawl-delay: 10`, and newenglandtrail.org [b4], `Crawl-delay: 3`.
# A reader that would build a query URL there refuses at import, so the
# layout test fails rather than the host being asked. Compared without a
# leading `www.`. A list a person edits, because robots.txt is read once per
# registration (decision 53, "Access is checked, never assumed"), not on
# every run.
QUERY_DISALLOWED_HOSTS = frozenset({"foothillstrail.org", "newenglandtrail.org"})


def _site(host: str | None) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def query_refused(url: str) -> str | None:
    """Why `url` may not carry a query string on its host, or None when it may."""
    host = _site(urlparse(url).hostname)
    if host in QUERY_DISALLOWED_HOSTS:
        return f"{host}'s robots.txt disallows every URL with a query string ('Disallow: /*?')"
    return None


# The statuses that are a host refusing us, not failing: never retried, never
# read as an empty answer. Measured in the inventory: 403 from Cloudflare's
# challenge (pcta.org [b2]), SiteDistrict's WAF (coloradotrail.org [b3]),
# Akamai (nyc.gov [b1]) and CloudFront (ncparks.gov/rss.xml [b3]); 429 from
# Vercel's Security Checkpoint (closures.pcta.org [b2]).
WALL_STATUSES = frozenset({401, 403, 429, 451})

# Response headers a challenge sets, and the value it sets them to (the
# inventory: `cf-mitigated: challenge` on pcta.org's 403 [b2],
# `x-vercel-mitigated: challenge` on closures.pcta.org's 429 [b2],
# `sg-captcha: challenge` on santafetrail.org's 202 with a meta refresh to
# /.well-known/sgcaptcha/ [b3]).
WALL_HEADERS = {"cf-mitigated": "challenge", "x-vercel-mitigated": "challenge", "sg-captcha": "challenge"}

# A challenge page's own <title>, for a wall that answers 200. The word
# "captcha" alone is NOT one: it was a form script on full 200 pages at
# pa.gov, yubaexpeditions.com and hillstosea.org [b1], and so is Cloudflare's
# passive /cdn-cgi/challenge-platform script, on aztrail.org's and
# tahoerimtrail.org's full pages [b1].
WALL_TITLES = frozenset({"just a moment...", "attention required! | cloudflare", "vercel security checkpoint"})

# Retried statuses: the server failing, not refusing. 429 is left out on
# purpose (WALL_STATUSES above).
RETRYABLE_STATUSES = (500, 502, 503, 504)


class NoticeUnreadable(RuntimeError):
    """The source answered, and not with a notice: a wall, a refusal, a moved page or a changed shape.

    Never an empty answer. The change check reads it as UNKNOWN; the read
    raises it, so the run leaves the resource out and its last rows stand.
    """


def wall(response: requests.Response) -> str | None:
    """What says this answer is a wall rather than the source, or None. Called on every answer, a 200 included."""
    if response.status_code in WALL_STATUSES:
        return f"HTTP {response.status_code}"
    for name, value in WALL_HEADERS.items():
        if (response.headers.get(name) or "").strip().lower() == value:
            return f"{name}: {value}"
    return None


def same_site(asked: str, served: str) -> bool:
    """Whether a redirect stayed on the asked host, counting `www.` as the same host.

    msgtc.org -> www.msgtc.org and friendsoftheouachita.org ->
    www.friendsoftheouachita.org are the same club's site [b1]; path-at.org ->
    www.piedmontathikers.org is another club's [b1], whose robots.txt and terms
    nobody read for this registry row.
    """
    return _site(urlparse(asked).hostname) == _site(urlparse(served).hostname)


# --- Politeness: one gap per host, across every reader and thread ----------

# The gap kept between two requests to one host when its robots.txt asks for
# none. @unvalidated: two seconds is decision 53's inventory rule ("at least
# 2 s between requests to one host otherwise", the session's worker brief), a
# courtesy, not a measurement of what any host can bear; what would settle it
# is a host telling us otherwise.
DEFAULT_HOST_GAP_SECONDS = 2.0


@dataclass
class _HostGate:
    lock: threading.Lock
    finished: float | None = None


_GATES: dict[str, _HostGate] = {}
_GATES_LOCK = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _pause(seconds: float) -> None:
    time.sleep(seconds)


def _gate(host: str) -> _HostGate:
    with _GATES_LOCK:
        return _GATES.setdefault(host, _HostGate(threading.Lock()))


def polite(http: requests.Session, delay: float) -> requests.Session:
    """`http`, with every request it sends held `delay` seconds after the last request to that host ended.

    One gate per host for the whole process, shared by every resource and
    every read_each thread, so two clubs on one host (aztrail.org serves
    `azgeo` and `ata` [b1, b4]) are never asked at once, and the gap is kept
    end to start, the stricter reading of a Crawl-delay. Each attempt
    lib/http_retry.py makes passes the gate too.
    """
    send = http.request

    def request(method, url, *args, **kwargs):
        gate = _gate(_site(urlparse(url).hostname))
        with gate.lock:
            if gate.finished is not None:
                wait = gate.finished + delay - _now()
                if wait > 0:
                    _pause(wait)
            try:
                return send(method, url, *args, **kwargs)
            finally:
                gate.finished = _now()

    http.request = request
    return http


# --- One request a run: the check's answer, kept for the read ---------------

# How long the read may use what the change check read, instead of asking
# again. Reasoned: since decision 61 these readers run on the notices legs,
# whose job is held to 60 minutes (extract-notices.yml), so an answer older
# than that is not this run's. It was 600, the conditions job's 10 minutes;
# on a notices leg the change checks alone may take 600 s
# (extract/_run.py's LEG_CHECK_SECONDS) before the first read starts, so 600
# would have sent the earliest-checked pages a second request every run.
REUSE_SECONDS = 3600

_ANSWERS: dict[str, tuple[float, object]] = {}
_ANSWERS_LOCK = threading.Lock()


def _remember(table: str, answer: object) -> None:
    with _ANSWERS_LOCK:
        _ANSWERS[table] = (_now(), answer)


def _forget(table: str) -> None:
    with _ANSWERS_LOCK:
        _ANSWERS.pop(table, None)


def _recall(table: str) -> object | None:
    """What this run's change check read for `table`, once: the parsed answer, or the exception it met."""
    with _ANSWERS_LOCK:
        kept = _ANSWERS.pop(table, None)
    if kept is None or _now() - kept[0] > REUSE_SECONDS:
        return None
    return kept[1]


def _conditional(recorded: dict | None) -> dict | None:
    headers = {}
    if recorded:
        if recorded.get("etag"):
            headers["If-None-Match"] = recorded["etag"]
        if recorded.get("last_modified"):
            headers["If-Modified-Since"] = recorded["last_modified"]
    return headers or None


@dataclass(frozen=True)
class _NoticeSource(Resource):
    """What both readers share: the registry row, the polite session, the guarded GET and the three-valued check."""

    # True only where the inventory measured the source's ETag or
    # Last-Modified as its own, so a 304 can mean FRESH. False (the default)
    # reads the source every run and compares a hash of what lands, because a
    # site-wide or request-time validator would answer FRESH while the source
    # moved (ELT.md, "The skip-unchanged check, by platform").
    trust_validators: bool = False
    # The host's robots.txt Crawl-delay, as the inventory read it; 0 when it
    # asks for none, which still keeps DEFAULT_HOST_GAP_SECONDS.
    crawl_delay: float = 0.0

    @property
    def entry(self) -> dict:
        return _kinds().registry_entry(self.key)

    @property
    def url(self) -> str:
        return self.entry["url"]

    @property
    def fetch_url(self) -> str:
        """The URL a check and a read ask: the registry row's, exactly as registered."""
        return self.url

    @property
    def timeout(self) -> int:
        return 60

    @property
    def exact_proof(self) -> bool:
        """The rows are built from the very answer the count is read from, so any difference is this code's mistake."""
        return True

    def _session(self) -> requests.Session:
        return polite(_kinds().session(), max(self.crawl_delay, DEFAULT_HOST_GAP_SECONDS))

    def _get(self, headers: dict | None = None) -> requests.Response:
        """One guarded GET of fetch_url: a wall, a moved host or a status that is not an answer raises NoticeUnreadable."""
        url = self.fetch_url
        try:
            response = request_with_retry(
                url,
                session=self._session(),
                headers=headers,
                timeout=self.timeout,
                retryable_statuses=RETRYABLE_STATUSES,
                label=self.key,
            )
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            kind = ", a wall; nothing is read past it" if status in WALL_STATUSES else ""
            raise NoticeUnreadable(f"{self.key}: {url} answered HTTP {status}{kind}") from error
        if reason := wall(response):
            raise NoticeUnreadable(f"{self.key}: {url} answered with a challenge ({reason}); not solved, not retried")
        if not same_site(url, response.url):
            raise NoticeUnreadable(
                f"{self.key}: {url} now redirects to {response.url}, another host, whose robots.txt and terms "
                "nobody has read for this row"
            )
        if response.status_code == 304:
            if headers is None:
                raise NoticeUnreadable(f"{self.key}: a 304 to a request that asked no condition")
            return response
        if response.status_code != 200:
            raise NoticeUnreadable(f"{self.key}: {url} answered HTTP {response.status_code}, which is not a notice")
        return response

    def _parse(self, response: requests.Response):
        """The rows and their proof, (rows, count), from one 200 answer. Raises on anything else."""
        raise NotImplementedError

    def _marker(self, rows: list[dict], response: requests.Response) -> dict:
        marker = {"rows": str(len(rows)), "sha256": _sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False))}
        if self.trust_validators:
            marker["etag"] = response.headers.get("ETag")
            marker["last_modified"] = response.headers.get("Last-Modified")
        return marker

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A conditional GET where the validators are the source's own, else the read itself and a hash of what lands.

        A 304 is FRESH and never reaches dlt, where it raises (the 2026-09-09
        spike). A 200 is parsed here, and FRESH only when what would land is
        exactly what the last committed load holds, so neither branch can
        answer FRESH while the rows moved. Anything this cannot read is
        UNKNOWN, which fetches; the read then raises what was met.
        """
        _forget(self.table)
        headers = _conditional(recorded) if self.trust_validators else None
        try:
            response = self._get(headers)
            if response.status_code == 304:
                return Freshness.FRESH, recorded
            rows, count = self._parse(response)
        except Exception as error:  # noqa: BLE001 - a check that errors is UNKNOWN (ELT.md); extract/_run.py stops the lane on any other raise
            _remember(self.table, error)
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        _remember(self.table, (rows, count))
        marker = self._marker(rows, response)
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        kept = _recall(self.table)
        if isinstance(kept, BaseException):
            raise kept
        rows, count = kept if kept is not None else self._parse(self._get())
        proofs[self.table] = count
        yield from (dict(row) for row in rows)


def _text(value: str | None) -> str | None:
    """Text with its runs of whitespace made one space, or None for none: BLM's titles carry a leading and trailing run [b4]."""
    value = " ".join((value or "").split())
    return value or None


# --- FeedNotices -------------------------------------------------------------

ATOM = "{http://www.w3.org/2005/Atom}"

# The columns a feed row lands, and nothing else: an allowlist, because a feed
# carries prose (description, content:encoded, Atom summary and content) and
# people (dc:creator, Atom author) that never load.
FEED_COLUMNS = (
    "item_id",
    "item_id_from",
    "title",
    "link",
    "published",
    "updated",
    "categories",
    "item_sha256",
    "feed_format",
    "feed_title",
    "feed_items",
    "listing",
    "_row",
)


# Every feed row's `listing`: the feed is its newest items, never the complete list (FeedNotices).
WINDOW = "window"


def _atom_link(entry: ElementTree.Element) -> str | None:
    links = entry.findall(f"{ATOM}link")
    for link in links:
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            return link.get("href").strip()
    return next((link.get("href").strip() for link in links if link.get("href")), None)


def _rss_item(item: ElementTree.Element) -> dict:
    guid = _text(item.findtext("guid"))
    link = _text(item.findtext("link"))
    if link is None and guid and (item.find("guid").get("isPermaLink") or "true").lower() != "false":
        link = guid
    return {
        "item_id": guid or link,
        "item_id_from": "guid" if guid else "link" if link else None,
        "title": _text(item.findtext("title")),
        "link": link,
        "published": _text(item.findtext("pubDate")),
        "updated": None,  # RSS 2.0 has no updated date; absent means unknown
        "categories": [text for c in item.findall("category") if (text := _text(c.text))],
    }


def _atom_entry(entry: ElementTree.Element) -> dict:
    entry_id = _text(entry.findtext(f"{ATOM}id"))
    link = _atom_link(entry)
    title = entry.find(f"{ATOM}title")
    return {
        "item_id": entry_id or link,
        "item_id_from": "id" if entry_id else "link" if link else None,
        "title": _text("".join(title.itertext())) if title is not None else None,
        "link": link,
        "published": _text(entry.findtext(f"{ATOM}published")),
        "updated": _text(entry.findtext(f"{ATOM}updated")),
        "categories": [text for c in entry.findall(f"{ATOM}category") if (text := _text(c.get("term") or c.get("label")))],
    }


def parse_feed(body: bytes) -> tuple[str, str | None, list[tuple[ElementTree.Element, dict]]]:
    """(format, the feed's own title, [(element, its item fields)]) from an RSS 2.0 or Atom document. Raises on any other.

    An empty <channel> or <feed> parses to no items, which is a feed with
    nothing in its window; a body that is neither raises, so an HTML error
    page answered with a 200 is never read as an empty feed.
    """
    root = ElementTree.fromstring(body)
    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("an <rss> document with no <channel>")
        return "rss", _text(channel.findtext("title")), [(item, _rss_item(item)) for item in channel.findall("item")]
    if root.tag == f"{ATOM}feed":
        title = root.find(f"{ATOM}title")
        feed_title = _text("".join(title.itertext())) if title is not None else None
        return "atom", feed_title, [(entry, _atom_entry(entry)) for entry in root.findall(f"{ATOM}entry")]
    raise ValueError(f"the answer is not RSS 2.0 or Atom (its root element is {root.tag!r})")


@dataclass(frozen=True)
class FeedNotices(_NoticeSource):
    """An RSS 2.0 or Atom feed's items, one row each: id, title, link, dates as the feed states them, categories.

    WHAT LANDS (FEED_COLUMNS). `item_id` is the RSS `guid` or the Atom `id`,
    or the link where an item has neither, and `item_id_from` says which; an
    item with none of the three cannot be told from the next, so the read
    raises. `published` (RSS `pubDate`, Atom `published`) and `updated` (Atom
    only) are the feed's own strings, unparsed, since a date this reader
    rewrote would be a date the feed did not state. `categories` is the list
    of category names (RSS text, Atom `term`), which places some notices by
    a closed vocabulary (AZT's 'Passage 38' [b1]). `item_sha256` hashes the
    whole item as served, prose included, so an edit to the body is seen
    without a word of it landing (decision 55). `feed_items` is the item
    count read from the same response, and the run check's proof: the rows
    are that count exactly (`exact_proof`). An empty channel is therefore a
    proven zero; a body that is not a feed raises, never a zero.

    AN RSS WINDOW IS NOT A LIST OF CURRENT ITEMS (the dlt skill, rule 4).
    Every row carries `listing = 'window'`: the feed holds its newest N
    items, so an item that ages out has not been lifted. Measured: AZT's
    closures feed held 10 of the category's 13 posts (X-WP-Total) [b1];
    CFPA's trail-notices feed 10 of the 30 its listing page shows [b5]; the
    Mid State Trail's 10 of 23 sections [b2]; ELT.md, 2026-10-01: AZT's 10
    went back to 2025-11-05 and NYSDEC's GovDelivery feed's 25 covered five
    days. So no dbt model may read absence from this table as an ending: a
    notice ends on its own end date or a rule for its source (ELT.md, "An
    RSS-fed closure ends only on an explicit signal"), and phase C's snapshot
    of this table keeps a row that leaves the window rather than closing it.
    Where a club also publishes the complete list (a WordPress category, a
    listing page), that list is the source and the feed is not.

    THE CHANGE CHECK. With `trust_validators`, a conditional GET with the
    feed's own ETag and Last-Modified: a 304 is FRESH and never reaches dlt.
    Without it (the default), the feed is read and FRESH only when the rows
    that would land hash the same as the last load's. The default is the
    safe one, because most feeds' validators are not their own (each from
    the inventory):

    - WordPress feed validators are site-wide, so they never decide FRESH for
      closures: GATC's /feed/ and /alerts/feed/ served the identical weak
      ETag W/"ea7e7b96…" and Last-Modified 11:32:58 GMT, newer than either
      channel's lastBuildDate [b4]; CFPA's Last-Modified read 2026-10-03
      02:39:58 while its newest item is 2026-07-17 [b5]; Hoosier Hikers
      Council's 2026-10-02 against a newest item of 2023-11-14 [b2].
    - Weebly's feeds (cvatclub.org, kta-hike.org) send no ETag and a
      Last-Modified equal to the request time [b5]; Wix's (mratc.org) send
      neither [b5]; Joomla's Atom feed (hike-mst.org) states `<updated>` as
      the request time and each item's 2012 creation date [b2].
    - BLM's press-release feeds send a strong ETag per feed ("1790988271"
      Montana-Dakotas, "1790988214" Alaska, "1790988305" Utah, each a Drupal
      page-cache time matching its Last-Modified) [b4, b5]. That a 304 there
      means the feed's bytes have not moved is Reasoned from Drupal
      regenerating the cached page when a node changes, and @unvalidated: no
      304 was observed; what would settle it is a 304 from one of those feeds
      followed, on the next 200, by an unchanged item hash. They are the one
      case for `trust_validators=True` so far.

    The validators ride the marker only when trusted, so a request-time
    Last-Modified cannot make every run read as changed.
    """

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in FEED_COLUMNS}
        hints.update(
            {"categories": {"data_type": "json"}, "feed_items": {"data_type": "bigint"}, "_row": {"data_type": "bigint"}}
        )
        return hints

    def _parse(self, response: requests.Response):
        feed_format, feed_title, items = parse_feed(response.content)
        rows = []
        for position, (element, fields) in enumerate(items):
            if fields["item_id"] is None:
                raise ValueError(f"{self.key}: item {position} has no guid, id or link, so it cannot be told from the next")
            rows.append(
                {
                    **fields,
                    "item_sha256": _sha256(ElementTree.tostring(element)),
                    "feed_format": feed_format,
                    "feed_title": feed_title,
                    "feed_items": len(items),
                    "listing": WINDOW,
                    "_row": position,
                }
            )
        return rows, len(items)


def feed_notices(key: str, *, trust_validators: bool = False, crawl_delay: float = 0.0, **overrides) -> FeedNotices:
    """A FeedNotices for a registry key; `trust_validators` only where the feed's ETag was measured as its own."""
    url = _kinds().registry_entry(key)["url"]  # an unregistered key fails at import, in the layout test
    if urlparse(url).query and (refused := query_refused(url)):
        raise ValueError(f"{key}: {refused}")
    return FeedNotices(key=key, trust_validators=trust_validators, crawl_delay=crawl_delay, **overrides)


# --- PageNotice --------------------------------------------------------------

# Elements whose text never reaches a title, a date or the region's hash: code
# and styling, and markup a page renders differently per request. ELT.md
# measured per-render tokens making a whole-body hash false-stale on
# Greenbelly, PNTA, CFPA's /trail-notices/ and the Long Path guide's
# `galleryId`; each sits in an attribute or a script, so a hash of the text
# outside these elements does not see them (Reasoned). Measured once:
# ncparks.gov's Mount Mitchell page, read by two inventory workers [b1, b3],
# served different bytes and gave the same region_sha256; the 8 other URLs
# read twice served identical bytes, so they test nothing.
SKIPPED_ELEMENTS = frozenset({"script", "style", "noscript", "template", "svg", "iframe"})
# Elements left out of the region's text and its stated date: site menus and
# footers change with the site, not the notice. amc-wma.org's 'This page last
# updated: 2026-04-14 05:44:51' is identical on two of its pages [b1], a site
# stamp, and sits in their <footer>: read with footers left out, both of its
# saved pages land no date (measured on the inventory's copies).
OUTSIDE_REGION = frozenset({"nav", "footer"})
VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)
# Elements that run on inside a line of text, so no space is put between
# their pieces; every other tag boundary is a word boundary.
INLINE_ELEMENTS = frozenset(
    {"a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "em", "font", "i", "kbd", "label", "mark", "q", "s",
     "samp", "small", "span", "strong", "sub", "sup", "time", "u", "var"}
)  # fmt: skip
# The region a page's notice is read from when the resource names none: the
# first of these the page has, so a theme's header and sidebar stay out where
# the page marks its main content. A fragment with none of them (mass.gov's
# alerts fragment [b1], NBATC's news fragment [b5]) is read whole, as
# `document`.
DEFAULT_REGIONS = ("main", "article", "body")
DOCUMENT = "document"


def _region_matcher(spec: str):
    """A test for one element, from `tag`, `#id`, `.class`, `tag#id` or `tag.class`."""
    match = re.fullmatch(r"([a-z][a-z0-9-]*)?(?:#([\w-]+)|\.([\w-]+))?", spec.strip().lower())
    if not match or not any(match.groups()):
        raise ValueError(f"region {spec!r} is not tag, #id, .class, tag#id or tag.class")
    tag, element_id, element_class = match.groups()

    def matches(name: str, attrs: dict) -> bool:
        if tag and name != tag:
            return False
        if element_id and (attrs.get("id") or "").lower() != element_id:
            return False
        return not element_class or element_class in (attrs.get("class") or "").lower().split()

    return matches


class _PageReader(HTMLParser):
    """One pass over a page: its <title>, og:title and JSON-LD blocks, and each candidate region's text and first <h1>.

    A region is the first element matching its spec, and everything inside
    it. `document` is always read too, for a page that has none of them.
    HTMLParser closes nothing by itself, so an end tag closes every element
    opened after its own start tag, the way a browser recovers from an
    unclosed <p> or <li>.
    """

    def __init__(self, specs: tuple[str, ...]):
        super().__init__(convert_charrefs=True)
        self.specs = specs
        self.matchers = [_region_matcher(spec) for spec in specs]
        self.stack: list[tuple[str, int | None]] = []  # (tag, the region it opened, if any)
        self.open = {len(specs)}  # region indexes being read; the last index is `document`
        self.text: dict[int, list[str]] = {len(specs): []}
        self.h1: dict[int, list[str]] = {len(specs): []}
        self.h1_done: set[int] = set()
        self.title: list[str] = []
        self.og_title: str | None = None
        self.json_ld: list[str] = []
        self._ld: list[str] | None = None
        self._skip = self._outside = self._h1 = 0
        self._in_title = False

    def _boundary(self, tag: str) -> None:
        if tag not in INLINE_ELEMENTS:
            for index in self.open:
                self.text[index].append(" ")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and (attrs.get("property") or "").lower() == "og:title" and self.og_title is None:
            self.og_title = attrs.get("content")
        self._boundary(tag)
        if tag in VOID_ELEMENTS:
            return
        opened = next(
            (i for i, matches in enumerate(self.matchers) if i not in self.text and matches(tag, attrs)),
            None,
        )
        if opened is not None:
            self.open.add(opened)
            self.text[opened], self.h1[opened] = [], []
        self.stack.append((tag, opened))
        if tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self._ld = []
        self._skip += tag in SKIPPED_ELEMENTS
        self._outside += tag in OUTSIDE_REGION
        self._h1 += tag == "h1"
        self._in_title = self._in_title or tag == "title"

    def handle_endtag(self, tag):
        self._boundary(tag)
        positions = [i for i, (name, _) in enumerate(self.stack) if name == tag]
        if tag in VOID_ELEMENTS or not positions:
            return  # an end tag nothing opened, which pages carry
        for name, opened in self.stack[positions[-1] :]:
            self.open.discard(opened)
            if name == "script" and self._ld is not None:
                self.json_ld.append("".join(self._ld))
                self._ld = None
            self._skip -= name in SKIPPED_ELEMENTS
            self._outside -= name in OUTSIDE_REGION
            if name == "h1":
                self._h1 -= 1
                self.h1_done.update(index for index in self.open if "".join(self.h1[index]).strip())
            self._in_title = self._in_title and name != "title"
        del self.stack[positions[-1] :]

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        elif self._skip:
            return
        elif self._in_title:
            self.title.append(data)
        elif not self._outside:
            for index in self.open:
                self.text[index].append(data)
                if self._h1 and index not in self.h1_done:
                    self.h1[index].append(data)

    def region(self, fallback: bool) -> tuple[str, str, str | None] | None:
        """(which region, its text, its first <h1>) for the first spec the page has, or `document`, or None."""
        indexes = [i for i in range(len(self.specs)) if i in self.text]
        if not indexes and not fallback:
            return None
        index = indexes[0] if indexes else len(self.specs)
        name = self.specs[index] if indexes else DOCUMENT
        return name, _text("".join(self.text[index])) or "", _text("".join(self.h1[index]))


def html_text(fragment: str) -> str:
    """A fragment of HTML as its visible text, whitespace folded: a WordPress title or rendered content."""
    reader = _PageReader(())
    reader.feed(fragment)
    reader.close()
    return reader.region(fallback=True)[1]


# A date a page states for itself: "Updated", "Update", "Last updated" or
# "updated on", an optional colon, then the date. Read off the pages the
# inventory measured: 'Updated August 17, 2026' (tahoerimtrail.org [b1]),
# 'Last Updated: August 27, 2026' (pnt.org [b4]), 'This page was updated on
# September 28, 2026.' (portland.gov [b2]), 'Knobstone Trail conditions
# Update: July 21, 2026' (in.gov [b2]), 'Last Update: September 30, 2026'
# (dnr.alaska.gov [b3]), 'Last updated: August 14, 2026' (nps.gov/natr [b4]),
# 'Update 7/30/2025' (nchighpeaks.org [b2]), 'Updated 9/4/26'
# (yubaexpeditions.com [b1]), 'Updated Sep. 24, 2026, 12:22 pm' (mass.gov
# [b1]). Numeric dates read month first: every one measured is a US club's,
# and each read that way (Reasoned). A date with no year ('Trail Update
# 4/13', foothillstrail.org [b1]) is not read: the year would be a guess.
_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_DATE = (
    r"(?P<date>(?P<month>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\.?\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})"
    r"|(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4}|\d{2})(?!\d)"
    r"|(?P<iso>\d{4}-\d{2}-\d{2}))"
)
STATED_DATE = re.compile(r"\b(?:last\s+)?updated?(?:\s+on)?\s*:?\s*" + _DATE, re.IGNORECASE)
# The date part alone, for a page whose own wording STATED_DATE does not
# match: a club file's `date_pattern` is its words around DATE, so DEC's
# backcountry page's header 'New this week (10/1/2026)' [b3] is
# `r"New this week \(" + DATE + r"\)"`. A listing whose items carry
# "Updated" stamps (USFS alert pages: 'UPDATED: April 16, 2026' on one card
# of the Chattahoochee-Oconee's; Duluth's press-release table: 'Trail
# Conditions Update 07/06/2012') has no page date to find, and takes
# `date_pattern=None`.
DATE = _DATE


def _stated_date(match: re.Match) -> date | None:
    """The day a match of DATE names, or None where it names no real day (a 31 September, an unknown month)."""
    group = match.groupdict()
    try:
        if group.get("iso"):
            return date.fromisoformat(group["iso"])
        if group.get("month"):
            word = group["month"].lower()
            word = "sep" if word == "sept" else word
            month = next((n for n, name in enumerate(_MONTHS, 1) if name.startswith(word)), None)
            return date(int(group["year"]), month, int(group["day"])) if month else None
        if group.get("y"):
            year = int(group["y"])
            return date(year + 2000 if year < 100 else year, int(group["m"]), int(group["d"]))
    except (TypeError, ValueError):
        return None
    return None


def page_stated_date(text: str, pattern: re.Pattern | None = STATED_DATE) -> tuple[str, str] | None:
    """(the date as the page states it, as an ISO day) for the newest update date the text states, or None.

    The newest, because a page that states several is saying when its
    newest part changed: Tahoe Rim Trail's 'Updated August 17, 2026' above
    nine segments stamped 'Last Updated: 6/24/26' to '7/7/26' [b1]. A date
    more than a day ahead of today is not a page's update date and is
    skipped, rather than published as one. A pattern of a club file's own
    embeds DATE, whose groups this reads.
    """
    if pattern is None:
        return None
    latest = datetime.now(UTC).date() + timedelta(days=1)
    found = [(stated, m.group("date")) for m in pattern.finditer(text) if (stated := _stated_date(m)) and stated <= latest]
    if not found:
        return None
    stated, as_written = max(found, key=lambda pair: pair[0])
    return as_written, stated.isoformat()


def _json_ld_modified(blocks: list[str]) -> str | None:
    """A page's JSON-LD dateModified: a *Page node's where the graph has one, as Yoast's does, else the first found."""
    found: list[tuple[bool, str]] = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if isinstance(node.get("dateModified"), str):
                kinds = node.get("@type")
                kinds = kinds if isinstance(kinds, list) else [kinds]
                found.append((any(isinstance(k, str) and k.endswith("Page") for k in kinds), node["dateModified"]))
            for value in node.values():
                walk(value)

    for block in blocks:
        try:
            walk(json.loads(block))
        except ValueError:
            continue  # a malformed block is the page's, and says nothing about its date
    return next((stamp for is_page, stamp in found if is_page), found[0][1] if found else None)


def _iso_day(stamp: str | None) -> str | None:
    return stamp[:10] if stamp and re.match(r"\d{4}-\d{2}-\d{2}", stamp) else None


def _http_day(stamp: str | None) -> str | None:
    try:
        return parsedate_to_datetime(stamp).date().isoformat() if stamp else None
    except (TypeError, ValueError):
        return None


def _decoded(response: requests.Response) -> str:
    """The page as text, in the charset it declares (header, then <meta>), else UTF-8; never requests' ISO-8859-1 guess."""
    declared = re.search(r"charset=([\w-]+)", response.headers.get("Content-Type") or "", re.IGNORECASE)
    if declared:
        name = declared.group(1)
    else:
        meta = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", response.content[:4096], re.IGNORECASE)
        name = meta.group(1).decode("ascii") if meta else "utf-8"
    try:
        return response.content.decode(name, errors="replace")
    except LookupError:
        return response.content.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class PdfFacts:
    """What a PDF says about itself: its text layer, page by page, and its metadata's dates as (as written, ISO day)."""

    texts: tuple[str, ...] = ()
    modified: tuple[str, str] | None = None
    created: tuple[str, str] | None = None


def read_pdf(body: bytes) -> PdfFacts:
    """A PDF's text layer and metadata dates, through pypdf, which requirements-extract.in pins and the build jobs do not.

    Imported here, as fetch_club_pdfs.py's extract_page_texts imports it, so
    nothing that only imports this module needs pypdf. A scanned PDF has no
    text layer (GATC's Blood_Mountain_Fire_Ban.pdf [b4]) and gives no texts.
    """
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(body))
    metadata = reader.metadata

    def stamp(name: str, attribute: str) -> tuple[str, str] | None:
        """A metadata date, or None where it is absent or unreadable: a malformed stamp is no date, not a failed read."""
        try:
            when = getattr(metadata, attribute) if metadata is not None else None
        except (TypeError, ValueError):
            return None
        return (str(metadata.get(name)), when.date().isoformat()) if when is not None else None

    return PdfFacts(
        texts=tuple(page.extract_text() or "" for page in reader.pages),
        modified=stamp("/ModDate", "modification_date"),
        created=stamp("/CreationDate", "creation_date"),
    )


# The columns a page notice lands, and nothing else.
PAGE_COLUMNS = ("url", "title", "date", "date_text", "date_source", "format", "region", "region_chars", "region_sha256")


@dataclass(frozen=True)
class PageNotice(_NoticeSource):
    """One notice per page: its title, its own stated date and which date that is, the link, and a hash of its notice region.

    The HTML-page and PDF rows of decision 53's phase B (ELT.md): 126 of the
    inventory's 356 notice URLs are web pages and 6 are PDFs, and no generic
    reader can tell one item on a page from the next, so the page is the
    notice. Nothing is parsed out of its prose into a closure: what lands is
    PAGE_COLUMNS, facts and a link (decision 55), never the page's wording.
    A page whose markup addresses items stably (USFS's alert cards, CFPA's
    `a.trail-notice-item`, mass.gov's action steps [b1, b5]) may get a
    per-item reader later, by the inventory's evidence; this is not it.

    THE ROW. `url` is the registry row's, the link a notice publishes.
    `title` is the region's first <h1>, else og:title, else <title>; a page
    with none of them has changed shape and raises, and `expect_title`, where
    set, must appear in it, so a page that turned into something else
    (nptrail.org's conditions URL now serves 'Trail Maps' [b1]) raises rather
    than publishing under its old name. A fragment that states no title of
    its own (mass.gov's alerts fragment, NBATC's news fragment [b1, b5]) sets
    `registry_title`, and carries the registry row's `title` instead.
    `region_sha256` hashes the region's visible text, whitespace folded, with
    scripts, styles, menus and footers left out; `region_chars` is that
    text's length, so a template with no message in it (CT DEEP's
    'Emergency Message - Parks' page, empty when read [b2]) can be told from
    a notice; `region` says what was read.

    THE DATE, as the page states it, in this order, and `date_source` says
    which one it is; `date_text` is the source's own string and `date` its
    ISO day. A page with none of them lands no date (absent means unknown):

    1. `page_text`: the newest update date the region states
       (page_stated_date(); the patterns measured are beside STATED_DATE).
       A page with its own wording sets a `date_pattern` around DATE, and
       `date_pattern=None` turns the step off for a page whose stamp is the
       site's or whose items carry their own (beside DATE).
    2. `json_ld`: the page's JSON-LD dateModified (ADK 2026-10-02T12:59:36Z,
       Tahoe Rim Trail 2026-08-17T21:09:14Z, Trustees 2026-09-16 [b1]); for a
       WordPress page read through REST, `wp_modified`, the post's own
       modified_gmt, which is the stamp Yoast writes there. On a PDF,
       `pdf_modified` then `pdf_created`, its metadata's ModDate and
       CreationDate.
    3. `last_modified`: the response's Last-Modified, and only with
       `trust_validators`, because on most pages it is the request time
       (Tahoe Rim Trail, CFPA's listing, BMTA, CDTC, EBRPD, hike-mst.org and
       aztrail.org [b1-b5]), and a page dated "now" is the display outrunning
       its source in the dangerous direction.

    A date never decides a change: AMC's conditions page states dateModified
    2026-02-18 above facility text dated 05/30/26 [b4], and TEHCC's
    generated maintenance log never moves its page's modified_gmt [b3].

    THE CHANGE CHECK. With `trust_validators`, a conditional GET with the
    page's own ETag and Last-Modified, and a 304 is FRESH. The inventory
    found few HTML pages whose validators could be their own:
    palmettotrail.org's Last-Modified (2026-08-25 on a 2026-10-03 read [b3])
    and DEC's backcountry page's (2026-10-02 20:32:31 [b3]) are older than
    the request, so not a generator's stamp, and the PDFs' strong ETags
    (friendsoftheouachita.org, thetrustees.org, bmtamail.org,
    georgia-atclub.org [b1, b3, b4]) are a static file's. Each was read once,
    so that they move only with the page is @unvalidated; what would settle
    it is a 304 followed, on the next 200, by an unchanged row hash.
    Everywhere else (the default) the page is read every run and FRESH only
    when the row hashes as the last load's, because the validators measured
    lie: blm.gov's alerts page's Drupal ETag and Last-Modified moved
    overnight with no item on it [b5]; the Nez Perce trail's fs.usda.gov
    page states the request time [b5]; portland.gov's weak ETag is the
    render time [b2]; tpwd.texas.gov's weak ETag was identical across pages
    [b2]; Squarespace's and Wix's weak ETags were each read once [b1, b4,
    b5].

    THREE WAYS IN, by what the registry row's url answers or the resource names:

    - HTML, the default, read from the url itself.
    - A WordPress page or post through its REST route, `wp_page=<id>` or
      `wp_post=<id>`: `<origin>/wp-json/wp/v2/pages/<id>`, with no query
      string, which foothillstrail.org's `Disallow: /*?` allows (its
      /wp-json/wp/v2/pages/25 answered 200 [b1]). The region is the post's
      rendered content; the date order is the same with `wp_modified` second.
      REST answers carry no HTTP validators (measured on OHTA, RATC, Mohonk
      and SHTA [b2, b3, b5]), so the check is the read.
    - A PDF, told by its Content-Type or `%PDF-` bytes: one notice per
      document, read over ClubPdf's fetch (a GET with a 120 s timeout). Its
      region is the whole file and `region_sha256` the bytes' sha256, the
      file being the unit (ELT.md, "An HTTP file"). Its title is the
      registry row's, because a PDF's own /Title is not the document's
      (GATC's water PDF embeds 'GATC Water Update July 2020.xlsx',
      sources.json), and its text layer is searched for a stated date.

    A WALL, A REFUSAL OR A MOVED PAGE IS UNKNOWN, AND THE LAST ROW STANDS
    (the module docstring). So is a 404 or 410: a URL that stopped answering
    is as likely a page that moved as a notice that ended (palmettotrail.org's
    closures post carries its date in its slug, so a new post moves the URL
    [b3]), so the read raises and the run says so every hour until a person
    looks, rather than reading the notice as lifted.
    """

    region: str | None = None
    wp_page: int | None = None
    wp_post: int | None = None
    expect_title: str | None = None
    registry_title: bool = False
    # The stated-date pattern; None turns step 1 of the date order off.
    date_pattern: str | None = STATED_DATE.pattern

    @property
    def wp_route(self) -> str | None:
        if self.wp_page is not None:
            return f"pages/{int(self.wp_page)}"
        if self.wp_post is not None:
            return f"posts/{int(self.wp_post)}"
        return None

    @property
    def fetch_url(self) -> str:
        """The registry row's url, or its WordPress REST route, which carries no query string."""
        if self.wp_route is None:
            return self.url
        parsed = urlparse(self.url)
        return f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2/{self.wp_route}"

    @property
    def timeout(self) -> int:
        """ClubPdf's 120 s for a PDF, which can be megabytes (GATC's 3_day_stay_order.pdf is 2,447,448 B [b4])."""
        return 120 if urlparse(self.url).path.lower().endswith(".pdf") else 60

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in PAGE_COLUMNS}
        hints["region_chars"] = {"data_type": "bigint"}
        return hints

    def _stated(self, text: str) -> tuple[str, str, str] | None:
        pattern = re.compile(self.date_pattern, re.IGNORECASE) if self.date_pattern else None
        stated = page_stated_date(text, pattern)
        return (*stated, "page_text") if stated else None

    def _last_modified(self, response: requests.Response) -> tuple[str, str, str] | None:
        stamp = response.headers.get("Last-Modified")
        day = _http_day(stamp)
        return (stamp, day, "last_modified") if self.trust_validators and day else None

    def _row(self, title: str | None, dated: tuple | None, fmt: str, region: str, text: str) -> dict:
        if not title:
            raise NoticeUnreadable(f"{self.key}: the page has no <h1>, og:title or <title>, which is a changed shape")
        if self.expect_title and self.expect_title.lower() not in title.lower():
            raise NoticeUnreadable(f"{self.key}: the page's title is now {title!r}, which no longer names {self.expect_title!r}")
        date_text, day, source = dated or (None, None, None)
        return {
            "url": self.url,
            "title": title,
            "date": day,
            "date_text": date_text,
            "date_source": source,
            "format": fmt,
            "region": region,
            "region_chars": len(text),
            "region_sha256": _sha256(text),
        }

    def _parse(self, response: requests.Response):
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "application/pdf" in content_type or response.content[:5] == b"%PDF-":
            return [self._pdf_row(response)], 1
        if self.wp_route is not None:
            return [self._wp_row(response)], 1
        return [self._html_row(response)], 1

    def _html_row(self, response: requests.Response) -> dict:
        reader = _PageReader((self.region,) if self.region else DEFAULT_REGIONS)
        reader.feed(_decoded(response))
        reader.close()
        title = _text("".join(reader.title))
        if title and title.lower() in WALL_TITLES:
            raise NoticeUnreadable(f"{self.key}: the page is a challenge ({title!r}); not solved, not retried")
        found = reader.region(fallback=self.region is None)
        if found is None:
            raise NoticeUnreadable(f"{self.key}: the page has no element matching {self.region!r}, which is a changed shape")
        region, text, h1 = found
        modified = _json_ld_modified(reader.json_ld)
        dated = (
            self._stated(text)
            or ((modified, _iso_day(modified), "json_ld") if _iso_day(modified) else None)
            or self._last_modified(response)
        )
        own = h1 or _text(reader.og_title) or title
        return self._row(own or (_text(self.entry.get("title")) if self.registry_title else None), dated, "html", region, text)

    def _wp_row(self, response: requests.Response) -> dict:
        try:
            post = response.json()
            title, content = post["title"]["rendered"], post["content"]["rendered"]
        except (ValueError, KeyError, TypeError) as error:
            raise NoticeUnreadable(f"{self.key}: {self.fetch_url} is not a WordPress post with a title and content") from error
        text = html_text(content)
        modified = post.get("modified_gmt")
        dated = self._stated(text) or ((modified, _iso_day(modified), "wp_modified") if _iso_day(modified) else None)
        return self._row(_text(html_text(title)), dated, "wp_rest", "wp:content", text)

    def _pdf_row(self, response: requests.Response) -> dict:
        facts = read_pdf(response.content)
        dated = (
            self._stated(" ".join(" ".join(page.split()) for page in facts.texts))
            or ((*facts.modified, "pdf_modified") if facts.modified else None)
            or ((*facts.created, "pdf_created") if facts.created else None)
            or self._last_modified(response)
        )
        row = self._row(_text(self.entry.get("title")), dated, "pdf", "pdf:bytes", "")
        return {**row, "region_chars": len(response.content), "region_sha256": _sha256(response.content)}


def page_notice(
    key: str,
    *,
    trust_validators: bool = False,
    crawl_delay: float = 0.0,
    region: str | None = None,
    wp_page: int | None = None,
    wp_post: int | None = None,
    expect_title: str | None = None,
    registry_title: bool = False,
    date_pattern: str | None = STATED_DATE.pattern,
    **overrides,
) -> PageNotice:
    """A PageNotice for a registry key. Every option is a per-site one, set from what the inventory read on that page."""
    url = _kinds().registry_entry(key)["url"]  # an unregistered key fails at import, in the layout test
    if wp_page is not None and wp_post is not None:
        raise ValueError(f"{key}: a page notice reads one WordPress page or one post, not both")
    if region is not None:
        _region_matcher(region)  # a malformed region fails at import
    if date_pattern is not None and "date" not in re.compile(date_pattern).groupindex:
        raise ValueError(f"{key}: a date_pattern embeds DATE, whose `date` group is the date it reads")
    if urlparse(url).query and (refused := query_refused(url)):
        raise ValueError(f"{key}: {refused}")
    return PageNotice(
        key=key,
        trust_validators=trust_validators,
        crawl_delay=crawl_delay,
        region=region,
        wp_page=wp_page,
        wp_post=wp_post,
        expect_title=expect_title,
        registry_title=registry_title,
        date_pattern=date_pattern,
        **overrides,
    )
