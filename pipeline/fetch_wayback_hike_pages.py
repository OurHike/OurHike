"""Recover NYNJTC's hike WRITE-UPS from the Internet Archive, ONCE (#1450).

    python fetch_wayback_hike_pages.py --index-only   just the listing
    python fetch_wayback_hike_pages.py                the listing and every page
    python fetch_wayback_hike_pages.py --limit 10     a sample, to look at

THE PAGE IS THE JOIN, and that is why this exists alongside
`fetch_wayback_hike_photos.py`. That fetcher recovers the photographs; this
one recovers the pages they sat on. A page carries the hike's NAME, its
LOCATION, its DESCRIPTION and its `<img>` in one document, written by the
people who walked it - so a photograph's hike is something this build READS
rather than infers. Every scoring heuristic in
`match_wayback_hike_photos.py` is a fallback for photographs whose page did
not survive; where a page did, the score is not needed and should not be
consulted.

`/view/hike` is the Drupal index that lists them, which is the piece the
first pass at this work never found - it went hunting for `/hikes/hike-<slug>`
(the WordPress era, 5 archived) and for `/hike-reviews/<n>` (a generic page)
and concluded the join was missing. It was not missing; it was at a path
nobody had looked at.

BE SLOW. THE ARCHIVE ALREADY REFUSED US ONCE. On 2026-09-15 a few hundred
reads at one per second - 60 a minute against a documented ceiling of about
15 - earned 429s, then 503s, then an outright refusal of the egress IP that
outlasted half an hour, so the listing could not be re-read at all. Both
fetchers now take from one process-wide limiter capped at ten a minute. web.archive.org
is donation-funded and owes this project nothing. A recovery that takes an
hour and finishes beats one that takes ten minutes and gets the client
banned, and this is a ONE-TIME job, so the slow version costs an afternoon
exactly once.

RESUMABLE, for the same reason its sibling is: a long job over a rate-limited
host WILL be interrupted, and a run that loses everything on the last request
is a run that gets attempted four times - which is four times the load on the
host that was already refusing us.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from lib.user_agent import CONTACTABLE_USER_AGENT as USER_AGENT
from lib.wayback_rate import ARCHIVE, MAX_REQUESTS_PER_MINUTE, REFUSALS, ArchiveRefusing

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = RAW_DIR / "wayback_hike_pages.json"

#: What this parser reads out of a write-up, as a number the cache carries.
#:
#: A RESUMED RUN SKIPS EVERY URL ALREADY IN THE CACHE, which is the whole
#: point of the cache and is wrong the moment the parser learns something new:
#: the rows are what an OLDER parser saw, and no amount of re-running reaches
#: them. Two changes have now done that - #1502 taught `coordinates()` the
#: bare pair these pages actually publish, and #1504 added the photographer's
#: credit - and in both cases a cached row is silently missing the new field.
#:
#: So the cache declares which parser wrote it, and a run that finds an older
#: number re-reads every write-up rather than resuming onto a cache it cannot
#: trust. That costs 878 archive requests, which is the price of the answer
#: being right; the alternative is a corpus reporting no coordinates and no
#: credits and looking exactly like one that has none.
#:
#: BUMP THIS whenever `parse_page` extracts something it did not before.
CACHE_FORMAT = 2

CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web"

#: The Drupal index that lists every hike - the maintainer's pointer, and the
#: path the first pass at this missed.
INDEX_URL = "nynjtc.org/view/hike"

#: The pacing is NOT a sleep here - `lib/wayback_rate.ARCHIVE` enforces a hard
#: rolling-window ceiling that a retry cannot slip past, which a sleep between
#: calls cannot: recovering ONE page is two requests (a CDX lookup and a
#: fetch), so a five-second pause after each yielded twelve a minute from a
#: loop that read as if it ran at six.

#: Backoff when it does push back, in seconds. Long, and long on purpose: the
#: archive's own Retry-After ran to 47s during that incident, and a retry that
#: returns before the host is ready just spends another refusal.
#: How often the partial cache is written, in write-ups. Small because the
#: file is tens of KB and the alternative is losing the run: a job killed at
#: its timeout keeps whatever the last save banked, and nothing else (#1522).
SAVE_EVERY = 10

RETRY_BACKOFF_SECONDS = (30, 120, 300)
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)
TIMEOUT = 120

#: `id_` asks for the archived bytes rather than the Wayback viewer's
#: rewritten page - the difference between reading NYNJTC's HTML and reading
#: the archive's chrome around it.
RAW = "id_"

_HIKE_HREF_RE = re.compile(r'href="([^"]*?/(?:hike|node)/[^"#?]+)"', re.I)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_U26_IMG_RE = re.compile(r'src="([^"]*?/u26/[^"]+\.(?:jpe?g|JPE?G))"')
_TAG_RE = re.compile(r"<[^>]+>")

#: THE LICENCE'S CONDITION, AS A REGEX (#1504).
#:
#: sources.json's `nynjtc_hikes_licence` does not merely ask for a credit, it
#: makes one the condition of the permission: "the attribution is a condition
#: rather than a courtesy: every photograph ships with the credit line the
#: page carries ('Photo by Daniel Chazin', 'Photo: Jane Daniels') ... and a
#: photograph the page does not credit is not fetched at all". So finding the
#: credit is not a nicety this parser adds; it is the thing that decides
#: whether a photograph may be used at all.
#:
#: MEASURED, on the wrong corpus. This pattern is carried verbatim from
#: `lib/nynjtc_hikes.py` as that module stood at c3be84f8^, where its comment
#: recorded the three spellings as measured across NYNJTC's twenty public
#: WordPress write-ups on 2026-09-09: "Photo by Daniel Chazin", "Photo: Jane
#: Daniels", "Photo credit: Daniela Wagstaff". Reusing it is better than
#: inventing one, because somebody did look at real pages to write it.
#:
#: @unvalidated AGAINST THESE PAGES. The archived corpus is the OLDER DRUPAL
#: site, a different CMS and a different theme, and nobody has read one of its
#: credit lines. What settles it is `--probe`, whose credit block already asks
#: exactly this question and has not yet got an answer past the archive's
#: throttle. Until it does, the direction of the error is the thing to be sure
#: of, and it is the safe one: a spelling this misses withholds a photograph,
#: it never ships an uncredited one.
_PHOTO_BY = re.compile(r"Photo(?:graph)?(?:\s+credit)?\s*(?:\bby\b|:)\s*([^.,;()\-\u2013\u2014]+)", re.IGNORECASE)

#: Which attributes on an `<img>` can hold a credit. Read as VALUES rather
#: than by running _PHOTO_BY over the raw tag: the pattern stops at
#: punctuation, and a tag ends in `" />`, so matching the tag text returned
#: `Daniel Chazin" />` as the photographer's name. Caught by a smoke test
#: before this ever ran, and the reason the tag is parsed rather than scanned.
_CREDIT_ATTR_RE = re.compile(r'\b(?:alt|title)="([^"]*)"', re.IGNORECASE)

#: The longest a photographer's name may be before this stops believing it.
#:
#: NOT a fact about names - it is a guard on the pattern. _PHOTO_BY ends its
#: capture at punctuation, and a credit whose sentence has none runs on into
#: whatever follows: the same smoke test returned "Daniela Wagstaff" followed
#: by 500 characters of body text. A capture this long is evidence the
#: pattern did not find the end of the name, so the honest answer is no
#: credit rather than a name with a paragraph stapled to it - which, under a
#: licence conditioned on the credit, is also the only safe answer.
MAX_CREDIT_CHARS = 60

#: How far past an `<img>` a caption may sit and still be that image's caption.
#:
#: @unvalidated - 600 characters is a guess at a Drupal caption block, not a
#: measurement, and `--probe` prints the surroundings that would replace it.
CAPTION_WINDOW_CHARS = 600

#: Tags that close nothing, so a scanner counting depth must not wait for
#: their closing tag. The HTML void elements, plus anything written `<x />`.
_VOID_TAGS = frozenset({"img", "br", "hr", "input", "meta", "link", "source", "area", "base", "col", "embed"})
_TAG_SHAPE_RE = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9]*)[^>]*?(/?)\s*>")

#: Drupal field labels on these write-ups. Read off the live markup rather
#: than assumed - a label this build guessed at would silently return nothing
#: and look like a page that carries no location.
_FIELD_RES = {
    "park": re.compile(r"field-name-field-park.*?field-item[^>]*>(.*?)<", re.I | re.S),
    "region": re.compile(r"field-name-field-region.*?field-item[^>]*>(.*?)<", re.I | re.S),
    "difficulty": re.compile(r"field-name-field-difficulty.*?field-item[^>]*>(.*?)<", re.I | re.S),
    "miles": re.compile(r"field-name-field-(?:length|miles).*?field-item[^>]*>(.*?)<", re.I | re.S),
}

#: A coordinate the page carries, in any of the shapes Drupal's mapping
#: modules emit. The maintainer's point - "the location probably is in the
#: text or link within the page" - and the reason this is worth parsing at
#: all: a hike with a coordinate can be matched to a photograph by DISTANCE
#: rather than by string overlap, which is a stronger claim.
_LATLON_RES = (
    re.compile(r'"lat(?:itude)?"\s*:\s*"?(-?\d+\.\d+)"?.{0,40}?"l(?:on|ng)(?:gitude)?"\s*:\s*"?(-?\d+\.\d+)"?', re.I | re.S),
    re.compile(r"data-lat=\"(-?\d+\.\d+)\"\s+data-l(?:on|ng)=\"(-?\d+\.\d+)\"", re.I),
    re.compile(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)", re.I),  # a Google Maps link
    re.compile(r"[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)", re.I),
    # A BARE PAIR, and it is last on purpose (#1502).
    #
    # The four above only know a coordinate that arrives LABELLED - behind a
    # JSON key, a data- attribute, or a Maps query parameter. These pages
    # publish it with nothing in front of it at all:
    # "41.195754000000,-74.184073000000". Measured on the 20230606152417
    # capture of /hike/claudius-smiths-rock, where that pair appears three
    # times and all four labelled patterns returned zero hits - which is how
    # the first full run reported a coordinate on NONE of 439 write-ups and
    # left the matcher's distance route unable to fire.
    #
    # Last, so a page that DOES label its coordinate is read by the pattern
    # that knows the label rather than by this one guessing.
    #
    # Three digits of fraction is the bar: it keeps this off "1.5,2.0" in a
    # stylesheet or a version string while accepting anything a geocoder
    # emits. What actually makes an unlabelled pair safe is the bounds check
    # in `coordinates()` - two decimals are only read as a place when they
    # land in the corner of the world these hikes are in.
    re.compile(r"(-?\d{1,3}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})"),
)


@dataclass(frozen=True)
class PagePhoto:
    """One photograph a write-up showed, and whether the page credits it.

    THE CREDIT IS WHY THIS IS A RECORD RATHER THAN A STRING (#1504). It was a
    bare filename until the licence was read properly: `nynjtc_hikes_licence`
    conditions the whole permission on the credit line, and a filename cannot
    carry one. Nothing downstream may offer a photograph whose `credit` is
    None - absent means unknown and unusable here, never "ship it
    uncredited".
    """

    filename: str
    #: The photographer the page names, or None when it names nobody.
    credit: str | None
    #: WHERE that name was found - `img`, `caption` or `page, sole
    #: photograph`. Carried because the three are not equally strong claims
    #: about WHICH photograph is credited, and a reviewer deciding whether to
    #: publish one should be told which of them they are looking at rather
    #: than handed a name with no provenance.
    credit_basis: str | None


@dataclass(frozen=True)
class HikePage:
    """One archived write-up, as the fields a match needs."""

    url: str
    timestamp: str
    name: str
    park: str | None
    region: str | None
    lat: float | None
    lon: float | None
    description: str
    #: The u26 photographs this page shows, each with the credit the page
    #: gives it. THE JOIN: these filenames are the same files
    #: fetch_wayback_hike_photos.py recovers, so a photograph's hike is read
    #: off the page rather than scored - AND the page is the only place the
    #: licence's required credit can come from, which is why these are
    #: records rather than names (#1504).
    photos: list[PagePhoto]


def session() -> requests.Session:
    made = requests.Session()
    made.headers["User-Agent"] = USER_AGENT
    return made


def get(made: requests.Session, url: str, params: dict | None = None) -> requests.Response | None:
    """One heavily-throttled, patiently-retried GET, or None once the archive
    has clearly had enough.

    Returning None rather than raising on a final refusal is deliberate here,
    unlike its sibling: this job is hundreds of pages and the host is the
    constraint, so one page the archive will not serve today is a page to come
    back for, not a reason to throw away everything already recovered. The
    caller records it as missing and moves on.

    THAT HOLDS FOR ONE PAGE AND NOT FOR A HUNDRED (#1522), which is what
    REFUSALS is for: a give-up here feeds the shared tripwire, and once
    enough of them arrive in a row this raises ArchiveRefusing through the
    caller's `continue` instead. Run 35092759225 is the case - every request
    refused for five and a half hours, the loop patiently moving on each
    time, 42 of 444 write-ups attempted and nothing written.

    A 404 is NOT a refusal. The archive answered; what it said is that it
    holds no capture. See lib/wayback_rate.Refusals for why that distinction
    decides whether the tripwire is honest.
    """
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        # Inside the loop, so a RETRY is counted too - see lib/wayback_rate.py.
        ARCHIVE.take()
        try:
            response = made.get(url, params=params or {}, timeout=TIMEOUT)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            if delay is None:
                print(f"    gave up on {url[:70]}: {type(error).__name__}", file=sys.stderr)
                REFUSALS.refused(f"{url[:70]}: {type(error).__name__}")
                return None
            print(f"    {type(error).__name__}; waiting {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        if response.status_code in RETRYABLE_STATUSES:
            if delay is None:
                print(f"    gave up on {url[:70]}: {response.status_code}", file=sys.stderr)
                REFUSALS.refused(f"{url[:70]}: {response.status_code}")
                return None
            wait = delay
            header = response.headers.get("Retry-After")
            if header and header.isdigit():
                wait = max(wait, int(header))
            print(f"    {response.status_code}; waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        # Final either way, so the host is answering us - a 404 included.
        REFUSALS.served()
        if response.status_code >= 400:
            return None
        return response
    return None


def latest_capture(made: requests.Session, url: str) -> tuple[str, str] | None:
    """The (original_url, timestamp) of `url`'s most recent archived copy."""
    response = get(
        made,
        CDX_API,
        {
            "url": url,
            "output": "json",
            "filter": "statuscode:200",
            "fl": "original,timestamp",
            # Duplicate captures of unchanged content collapse to one row.
            "collapse": "digest",
        },
    )
    if response is None:
        return None
    try:
        rows = response.json()
    except ValueError:
        return None
    if len(rows) < 2:
        return None
    best = max(rows[1:], key=lambda r: r[1])
    return best[0], best[1]


def archived(url: str, timestamp: str) -> str:
    return f"{WAYBACK}/{timestamp}{RAW}/{url}"


def strip_tags(markup: str) -> str:
    return " ".join(_TAG_RE.sub(" ", markup).split())


def hike_links(markup: str) -> list[str]:
    """Every hike write-up the index points at, absolute and deduped.

    The archive rewrites hrefs to its own `/web/<timestamp>/<original>` form,
    so the original URL has to be dug back out - taking the rewritten one
    would ask the archive to archive its own archive.
    """
    found = []
    for href in _HIKE_HREF_RE.findall(markup):
        original = href
        marker = "/http"
        if "/web/" in href and marker in href:
            original = href[href.index(marker) + 1 :]
        elif href.startswith("/"):
            original = f"https://www.nynjtc.org{href}"
        original = original.split("?")[0].rstrip("/")
        if "/hike/" in original or "/node/" in original:
            found.append(original)
    return sorted(dict.fromkeys(found))


def coordinates(markup: str) -> tuple[float, float] | None:
    """A latitude and longitude the page carries, or None.

    Bounded to the region these hikes are in rather than accepted blindly: a
    Drupal page is full of numbers, and a regex that matched a pair of them
    anywhere would put a hike in the Atlantic. NY/NJ/PA corner, generously.
    """
    for pattern in _LATLON_RES:
        # EVERY match, not just the first (#1502). `search()` took one match
        # per pattern, so a match that failed the bounds below moved on to the
        # next PATTERN rather than the next match - discarding a good
        # coordinate sitting further down the page. Latent while every pattern
        # was a labelled shape that appears once; live the moment the bare
        # pair above is in the list, because an 82 KB Drupal page has several.
        for found in pattern.finditer(markup):
            try:
                lat, lon = float(found.group(1)), float(found.group(2))
            except (TypeError, ValueError):
                continue
            if 38.0 <= lat <= 44.0 and -78.0 <= lon <= -71.0:
                return lat, lon
    return None


def text_nodes(markup: str) -> list[str]:
    """Each run of text between tags, unescaped, in order.

    The unit a credit is searched in, and deliberately NOT `strip_tags`'s one
    long string. A credit is written as its own caption or paragraph, so the
    tag boundary IS the end of the name - and flattening the tags away
    deletes exactly the boundary that stops _PHOTO_BY reading on into the
    next sentence.

    KNOWN MISS, and left as one on purpose: a credit split across a tag
    ("Photo by <a>Daniel Chazin</a>") arrives here as two nodes and matches
    nothing, so that photograph is withheld. Joining the nodes to catch it
    would also join two unrelated paragraphs and could name the wrong
    photographer - and misattributing a real person's work is a worse failure
    than not publishing a picture. `--probe` is what says whether these pages
    write it that way at all.
    """
    return [text for text in (html_module.unescape(chunk).strip() for chunk in _TAG_RE.split(markup)) if text]


def enclosing_caption(markup: str, start: int, stop: int) -> str:
    """The markup from `start` that is still INSIDE the image's own container.

    THE BOUND THAT STOPS A MIS-ATTRIBUTION, and two weaker ones did not.

    Bounding only by the next u26 image is enough for a gallery and nothing
    for the LAST image on a page: there is no next image, so the window ran
    on, and `<div><img></div><div id=footer><p>Photo by Daniel Chazin</p>`
    credited the article's photograph to the site's footer. Review reproduced
    that. Counting text runs instead does not fix it either - `</p></div>
    <div id=footer><p>` yields no text at all, so the footer's credit is
    still the second run.

    What separates a caption from a footer is STRUCTURE, so that is what is
    measured: walk forward counting tags, and stop at the first closing tag
    that would leave the element the image was in. A caption sits beside the
    picture inside that element; a footer is outside it by construction.

    Text already written before that closing tag is kept, so
    `<p>… <img> Photo by X</p>` - an image inline in a paragraph - still
    yields its own paragraph.
    """
    depth = 0
    for tag in _TAG_SHAPE_RE.finditer(markup, start, stop):
        closing, name, self_closing = tag.group(1), tag.group(2).lower(), tag.group(3)
        if closing:
            if depth == 0:
                return markup[start : tag.start()]
            depth -= 1
        elif not self_closing and name not in _VOID_TAGS:
            depth += 1
    return markup[start:stop]


def photo_credit(*texts: str) -> str | None:
    """The photographer named in any of these fragments, or None.

    Carried from `lib/nynjtc_hikes.photo_credit` (at c3be84f8^, before the
    WordPress fetcher it belonged to was withdrawn under #1427) so the two
    roads to NYNJTC's photographs answer the licence's condition the same
    way rather than two ways. MAX_CREDIT_CHARS is the one thing added to it,
    for the reason recorded there.

    TAKES TEXT, NOT MARKUP. Both callers unescape before handing anything
    over, because _PHOTO_BY stops at `;` and would cut a name at an entity.
    Unescaping again here would turn a page's literal `Smith &amp;amp; Co`
    into `Smith & Co` - a credit that is not what the page says, which on a
    licence conditioned on the credit is the one thing this must not invent.
    """
    for text in texts:
        found = _PHOTO_BY.search(text or "")
        if found:
            name = " ".join(found.group(1).split()).strip()
            if name and len(name) <= MAX_CREDIT_CHARS:
                return name
    return None


def page_photos(markup: str) -> list[PagePhoto]:
    """Every u26 photograph this page shows, with the credit the page gives it.

    TWO PLACES A CREDIT MAY BE READ FROM, and both are ATTACHED to the image
    rather than merely present on the page:

    1. `img` - inside the `<img>` tag itself, in its alt or title text. Names
       the photograph directly and cannot be confused with another.
    2. `caption` - the markup after the tag that is still inside the image's
       own container (`enclosing_caption`), stopping at the next u26 image or
       CAPTION_WINDOW_CHARS, whichever comes first. The WordPress corpus put
       the credit in the
       paragraph under the figure on six of twenty pages (measured
       2026-09-09, `lib/nynjtc_hikes.py` at c3be84f8^), so "outside the tag"
       is where a credit demonstrably lives and not a case invented here.

    THERE WAS A THIRD AND IT WAS WRONG. `page, sole photograph` read a credit
    from anywhere in the document when the page showed exactly one u26 image,
    on the argument that there was then nothing else it could be about. There
    was: "sole" counted only u26 images, so a page with a news teaser
    elsewhere - `<img src="/news/bear.jpg"><p>Bears return. Photo by Jane
    Daniels</p>` - handed Jane Daniels' name to an entirely different
    photograph, which review reproduced. Nothing measured supported the route
    (the six WordPress pages put their credits in the caption, which route 2
    reads), and attaching a real photographer's name to somebody else's
    picture is the worst thing this parser can do. So it is gone rather than
    narrowed: a route that cannot be made safe without markup nobody has seen
    is a route to leave out until `--probe` has seen it.

    WHAT REMAINS IS THE SAFETY ARGUMENT. Both surviving routes are bounded to
    the image, so the only thing a missing credit causes is a photograph being
    withheld - the direction CLAUDE.md's "omit rather than guess" asks for on
    a licence condition as much as on a water distance.

    A filename shown twice (a thumbnail and the full image are one photograph)
    is deduped, keeping the strongest credit found for it.
    """
    hits = list(_U26_IMG_RE.finditer(markup))

    found: dict[str, PagePhoto] = {}
    for index, hit in enumerate(hits):
        filename = urllib.parse.unquote(hit.group(1).rsplit("/", 1)[-1])

        # The tag this src sits in: back to its "<" and forward to its ">",
        # so alt= and title= are read whichever side of src= they were written.
        opened = markup.rfind("<", 0, hit.start())
        closed = markup.find(">", hit.end())
        tag = markup[opened if opened != -1 else hit.start() : closed + 1 if closed != -1 else hit.end()]

        # ...and the markup after it, bounded by the next photograph so a
        # gallery cannot hand this one's credit to the next.
        after_from = closed + 1 if closed != -1 else hit.end()
        after_to = after_from + CAPTION_WINDOW_CHARS
        if index + 1 < len(hits):
            after_to = min(after_to, hits[index + 1].start())
        caption = enclosing_caption(markup, after_from, max(after_from, after_to))

        # Unescaped BEFORE matching, not after: _PHOTO_BY stops at `;`, so
        # `alt="Photo by Jos&eacute; Ramos"` matched as written returns the
        # surname-less "Jos&eacute". text_nodes() already does this, which is
        # why only the attribute route needed saying.
        attributes = [html_module.unescape(value) for value in _CREDIT_ATTR_RE.findall(tag)]

        credit, basis = photo_credit(*attributes), "img"
        if credit is None:
            credit, basis = photo_credit(*text_nodes(caption)), "caption"
        if credit is None:
            basis = None

        previous = found.get(filename)
        if previous is None or (previous.credit is None and credit is not None):
            found[filename] = PagePhoto(filename=filename, credit=credit, credit_basis=basis)

    return sorted(found.values(), key=lambda photo: photo.filename)


def parse_page(markup: str, url: str, timestamp: str) -> HikePage | None:
    """One write-up's fields, or None when this is not a hike page at all."""
    title = _TITLE_RE.search(markup)
    name = strip_tags(title.group(1)) if title else ""
    for suffix in (" | New York-New Jersey Trail Conference", " - New York-New Jersey Trail Conference"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    name = name.removeprefix("Hike:").removeprefix("Hike -").strip()
    if not name:
        return None

    fields = {}
    for key, pattern in _FIELD_RES.items():
        found = pattern.search(markup)
        fields[key] = strip_tags(found.group(1)).strip() if found else None

    photos = page_photos(markup)
    where = coordinates(markup)

    body = strip_tags(markup)
    return HikePage(
        url=url,
        timestamp=timestamp,
        name=name,
        park=fields.get("park"),
        region=fields.get("region"),
        lat=where[0] if where else None,
        lon=where[1] if where else None,
        description=body[:4000],
        photos=photos,
    )


def load_done(path: Path | None = None) -> dict[str, HikePage]:
    path = path or OUT_PATH
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if document.get("format") != CACHE_FORMAT:
        # SAID OUT LOUD, because the first version of this dropped the rows
        # in silence. `HikePage(**row)` raised TypeError on a pre-#1504 row
        # (its `photos` were bare strings), the `except` swallowed it, and
        # `main()`'s "N already recovered" line is inside an `if pages:` - so
        # a run resumed onto a 439-page cache printed nothing at all and
        # re-fetched the lot. Losing the cache is the RIGHT answer here;
        # losing it without telling anybody is not.
        print(f"  {path.name} was written by parser format {document.get('format')!r}, this is {CACHE_FORMAT}.")
        print("  Re-reading every write-up: the cached rows predate the coordinate (#1502)")
        print("  and credit (#1504) parsers, and a resumed run would never revisit them.")
        return {}
    done = {}
    for row in document.get("pages", []):
        try:
            fields = dict(row)
            # asdict() flattened the records on the way out; rebuild them, or
            # a resumed run would carry dicts where the rest of this module
            # expects PagePhoto and lose the credit gate on every page it
            # did not fetch itself.
            fields["photos"] = [PagePhoto(**photo) for photo in fields.get("photos") or []]
            done[row["url"]] = HikePage(**fields)
        except (TypeError, KeyError):
            continue
    return done


def write_cache(pages: list[HikePage], links: list[str], path: Path | None = None) -> None:
    path = path or OUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source": "web.archive.org",
                "format": CACHE_FORMAT,
                "index": INDEX_URL,
                "one_time": True,
                "listed": len(links),
                "pages": [asdict(p) for p in pages],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def probe(made, url: str) -> int:
    """Fetch ONE archived write-up and say what a coordinate parser can see in it.

    WHY THIS EXISTS (#1497). The first full run recovered 439 write-ups and
    found a coordinate in **none** of them. That is either a fact about the
    corpus - in which case the matcher's distance route can never fire and
    says so - or it is `_LATLON_RES` missing the shape these pages use, which
    is a bug. Zero out of 439 is exactly what a broken regex looks like, so
    the two have to be told apart rather than guessed between.

    It could not be told apart from an agent sandbox: web.archive.org refuses
    that egress address, and the environment's fetch tools decline the host
    outright. So the question comes here, where two requests answer it.

    Prints what EACH pattern found and a raw window around any "lat" in the
    markup, because "no pattern matched" and "the page has no coordinate" are
    different answers and only the second one is a finding.
    """
    print(f"Probing {url}")
    found = latest_capture(made, url.replace("https://", "").replace("http://", ""))
    if found is None:
        print("  the archive would not name a capture of it")
        return 1
    page_url, page_ts = found
    print(f"  most recent capture {page_ts}")

    response = get(made, archived(page_url, page_ts))
    if response is None:
        print("  the capture would not fetch")
        return 1
    markup = response.text
    print(f"  {len(markup)} bytes of markup")

    print()
    for index, pattern in enumerate(_LATLON_RES, 1):
        hits = pattern.findall(markup)
        print(f"  pattern {index}: {len(hits)} hit(s){' -> ' + str(hits[:3]) if hits else ''}")

    where = coordinates(markup)
    print(f"  coordinates() -> {where}")

    # The fallback question: is anything coordinate-SHAPED in there at all? A
    # bare decimal pair near a latitude-ish word is what a fifth pattern would
    # have to match, and seeing the surrounding characters is what says which
    # one to write.
    print()
    windows = [markup[max(0, m.start() - 60) : m.start() + 120] for m in re.finditer(r"(?i)lat(?:itude)?", markup)]
    print(f"  {len(windows)} mention(s) of lat/latitude in the markup")
    for window in windows[:5]:
        print("    ..." + " ".join(window.split()) + "...")

    # WITH THEIR SURROUNDINGS (#1502). The first version printed the numbers
    # alone, which was enough to prove the parser wrong and not enough to
    # write the replacement: a bare pair could be a coordinate, a bounding-box
    # corner or a stylesheet value, and only the markup around it says which.
    pairs = list(re.finditer(r"-?\d{1,3}\.\d{3,}\s*[,;]\s*-?\d{1,3}\.\d{3,}", markup))
    print(f"  {len(pairs)} bare decimal pair(s)")
    for hit in pairs[:5]:
        window = markup[max(0, hit.start() - 80) : hit.end() + 40]
        print("    ..." + " ".join(window.split()) + "...")

    # THE MARKUP AROUND EACH IMAGE (#1504), because the credit line is the
    # licence's condition and nobody has seen where it lives. sources.json's
    # nynjtc_hikes_licence says "every photograph ships with the credit line
    # the page carries ('Photo by Daniel Chazin')" and "a photograph the page
    # does not credit is not fetched at all" - and the recovery so far
    # selected by directory prefix, so it has 403 images of which 9 carry a
    # credit anywhere.
    #
    # A wide window on both sides: a Drupal credit can sit in the alt text, in
    # a figcaption after the img, or in a sibling field div before it, and
    # guessing which would repeat exactly the mistake that made coordinates()
    # return None on 439 pages.
    print()
    parsed = page_photos(markup)
    print(f"  {len(parsed)} u26 image(s), as page_photos() reads them")
    for photo in parsed[:6]:
        credit = f"{photo.credit} (from {photo.credit_basis})" if photo.credit else "NO CREDIT - unusable"
        print(f"    {photo.filename}  ->  {credit}")

    # THE CREDIT, asked directly rather than by dumping markup (#1504).
    #
    # The first version of this printed 800 characters of raw markup either
    # side of each image, and the answer never arrived: those lines are so fat
    # that the job log's tail could not reach them. Asking the narrow question
    # - where does credit-shaped text appear, and what does it look like -
    # fits in the log AND is the thing actually being decided.
    #
    # The patterns are the shapes sources.json's nynjtc_hikes_licence quotes
    # ("Photo by Daniel Chazin", "Photo: Jane Daniels") plus the Drupal field
    # names a credit usually hides behind.
    print()
    for label, pattern in (
        ("photo by", r"(?i)photo\s+by"),
        ("photo:", r"(?i)photo\s*:"),
        ("credit", r"(?i)credit"),
        ("courtesy", r"(?i)courtesy"),
        ("field-.*credit", r"(?i)field-[a-z-]*credit"),
    ):
        hits = list(re.finditer(pattern, markup))
        print(f"  {label:18} {len(hits)} hit(s)")
        for hit in hits[:3]:
            window = markup[max(0, hit.start() - 70) : hit.end() + 90]
            print("      ..." + " ".join(window.split()) + "...")
    return 0


def recover_page(made: requests.Session, link: str) -> tuple[HikePage | None, bool]:
    """One write-up, and whether the archive gave us anything to parse.

    TWO ANSWERS RATHER THAN ONE, because the summary tells them apart and a
    reader of it should be able to: `archive refused` counts captures the
    archive would not serve, while a page that arrived and did not parse is a
    fact about the page. Folded together they would report a corpus problem
    as a host problem, which is the confusion this whole module is careful
    about everywhere else.

    Extracted for #1522. The `continue`s this replaces sat above main()'s
    periodic `write_cache`, so the save was reachable only on an iteration
    that recovered something - and a run where every page failed wrote
    nothing at all before its job timeout killed it.
    """
    found = latest_capture(made, link.replace("https://", "").replace("http://", ""))
    if found is None:
        return None, False
    page_url, page_ts = found
    page_response = get(made, archived(page_url, page_ts))
    if page_response is None:
        return None, False
    return parse_page(page_response.text, link, page_ts), True


def main(limit: int | None, index_only: bool) -> int:
    made = session()

    print(f"Finding the most recent capture of {INDEX_URL} ...")
    capture = latest_capture(made, INDEX_URL)
    if capture is None:
        print("The archive would not serve the index. It was refusing this client earlier today;")
        print("wait longer rather than retrying in a loop - see lib/wayback_rate.py.")
        return 1
    index_url, index_ts = capture
    print(f"  {index_ts} {index_url}")

    response = get(made, archived(index_url, index_ts))
    if response is None:
        print("The index capture could not be fetched. Same advice: wait.")
        return 1

    links = hike_links(response.text)
    print(f"  {len(links)} hike write-ups listed")
    if index_only or not links:
        for link in links[:20]:
            print(f"    {link}")
        return 0 if links else 1

    done = load_done()
    todo = [link for link in links if link not in done]
    pages = [done[link] for link in links if link in done]
    if pages:
        print(f"  {len(pages)} already recovered; {len(todo)} to go")
    todo = todo[:limit] if limit else todo

    print(f"\nFetching {len(todo)} write-ups, capped at {MAX_REQUESTS_PER_MINUTE}/min - slow on purpose.")
    missed = 0
    refusing: ArchiveRefusing | None = None
    for index, link in enumerate(todo, 1):
        try:
            parsed, served = recover_page(made, link)
        except ArchiveRefusing as trip:
            # Not an error to swallow and not one to escape: the rows already
            # recovered are written below, and THEN this is reported.
            refusing = trip
            break
        if parsed:
            pages.append(parsed)
        if not served:
            missed += 1
        # EVERY iteration reaches this, which is the #1522 fix. It used to sit
        # under two `continue`s and so ran only when a page came back.
        if index % SAVE_EVERY == 0:
            write_cache(pages, links)
            with_photo = sum(1 for p in pages if p.photos)
            print(f"  {index}/{len(todo)} ... {len(pages)} parsed, {with_photo} carry a photo")

    write_cache(pages, links)

    with_photo = [p for p in pages if p.photos]
    with_credit = [p for p in pages if any(photo.credit for photo in p.photos)]
    with_coords = [p for p in pages if p.lat is not None]
    shown = [photo for p in pages for photo in p.photos]
    credited = [photo for photo in shown if photo.credit]
    print()
    print(f"  listed              {len(links)}")
    print(f"  recovered           {len(pages)}")
    print(f"  carry a photo       {len(with_photo)}")
    print(f"  ...credited         {len(with_credit)}")
    print(f"  carry a coord       {len(with_coords)}")
    print(f"  archive refused     {missed}")
    print()
    print(f"  photographs shown   {len(shown)}")
    print(f"  ...with a credit    {len(credited)}")
    for basis in ("img", "caption", "page, sole photograph"):
        count = sum(1 for photo in credited if photo.credit_basis == basis)
        if count:
            print(f"      from {basis:22} {count}")
    print()
    print(f"  written to {OUT_PATH}")
    print("  Each photo filename here is a READ join to a hike, not a scored one.")
    # THE NUMBER THAT DECIDES WHAT MAY SHIP (#1504). sources.json's
    # nynjtc_hikes_licence makes the credit a condition, so "with a credit" is
    # the size of the usable corpus and "photographs shown" is not. A zero
    # here is a finding about the parser as much as about the pages - see
    # _PHOTO_BY, which is @unvalidated against this Drupal markup - and
    # `--probe` is what tells the two apart.
    if shown and not credited:
        print()
        print("  NOT ONE of those photographs carries a credit this parser can see.")
        print("  That is either the corpus or _PHOTO_BY missing the Drupal spelling;")
        print("  run --probe on one of these URLs before believing either.")

    # LAST, and after the cache is on disk, so the rows survive the report
    # (#1522). The exit code is what stops the workflow's later stages asking
    # the same host the same question for another five hours.
    if refusing is not None:
        print()
        print(f"  STOPPED EARLY: {refusing}")
        print(f"  {len(pages)} write-ups are written and a later run resumes onto them.")
        print("  Re-dispatch rather than retrying in a loop: a fresh runner is a fresh")
        print("  address, and the archive is donation-funded and owes us nothing.")
        return 1
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="Fetch only the first N write-ups.")
    parser.add_argument("--index-only", action="store_true", help="List what the index points at; fetch no pages.")
    parser.add_argument(
        "--probe",
        metavar="URL",
        default=None,
        help="Fetch ONE write-up and report what each coordinate pattern sees in it (#1497).",
    )
    args = parser.parse_args(argv)
    if args.probe:
        return probe(session(), args.probe)
    return main(args.limit, args.index_only)


if __name__ == "__main__":
    raise SystemExit(run())
