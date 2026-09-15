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

BE SLOW. THE ARCHIVE ALREADY REFUSED US ONCE, and this is the reason
`THROTTLE_SECONDS` is what it is rather than the 1.0 its sibling uses. On
2026-09-15 a few hundred reads at one per second earned 429s, then 503s, then
connection resets that lasted past half an hour - so the listing could not be
re-read at all for a while. web.archive.org is donation-funded and owes this
project nothing. A recovery that takes an hour and finishes beats one that
takes ten minutes and gets the client blocked, and this is a ONE-TIME job, so
the slow version costs an afternoon exactly once.

RESUMABLE, for the same reason its sibling is: a long job over a rate-limited
host WILL be interrupted, and a run that loses everything on the last request
is a run that gets attempted four times - which is four times the load on the
host that was already refusing us.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from lib.user_agent import CONTACTABLE_USER_AGENT as USER_AGENT

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = RAW_DIR / "wayback_hike_pages.json"

CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web"

#: The Drupal index that lists every hike - the maintainer's pointer, and the
#: path the first pass at this missed.
INDEX_URL = "nynjtc.org/view/hike"

#: Seconds between requests. FIVE, not one.
#:
#: MEASURED THE HARD WAY, 2026-09-15: a few hundred reads at 1.0s earned 429
#: (with Retry-After in the 30-50s range), then 503, then connection resets
#: that outlasted a thirty-minute pause. At that point the CDX listing itself
#: could not be fetched, so the job could not even find out what it still
#: needed. This number is not politeness, it is the difference between a run
#: that finishes and a client that gets refused.
THROTTLE_SECONDS = 5.0

#: Backoff when it does push back, in seconds. Long, and long on purpose: the
#: archive's own Retry-After ran to 47s during that incident, and a retry that
#: returns before the host is ready just spends another refusal.
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
)


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
    #: The u26 filenames this page shows. THE JOIN: these are the same files
    #: fetch_wayback_hike_photos.py recovers, so a photograph's hike is read
    #: off the page rather than scored.
    photos: list[str]


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
    """
    for attempt, delay in enumerate((*RETRY_BACKOFF_SECONDS, None)):
        try:
            response = made.get(url, params=params or {}, timeout=TIMEOUT)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            if delay is None:
                print(f"    gave up on {url[:70]}: {type(error).__name__}", file=sys.stderr)
                return None
            print(f"    {type(error).__name__}; waiting {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        if response.status_code in RETRYABLE_STATUSES:
            if delay is None:
                print(f"    gave up on {url[:70]}: {response.status_code}", file=sys.stderr)
                return None
            wait = delay
            header = response.headers.get("Retry-After")
            if header and header.isdigit():
                wait = max(wait, int(header))
            print(f"    {response.status_code}; waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if response.status_code >= 400:
            return None
        time.sleep(THROTTLE_SECONDS)
        return response
    return None


def latest_capture(made: requests.Session, url: str) -> tuple[str, str] | None:
    """The (original_url, timestamp) of `url`'s most recent archived copy."""
    response = get(made, CDX_API, {"url": url, "output": "json", "filter": "statuscode:200", "fl": "original,timestamp"})
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
        found = pattern.search(markup)
        if not found:
            continue
        try:
            lat, lon = float(found.group(1)), float(found.group(2))
        except (TypeError, ValueError):
            continue
        if 38.0 <= lat <= 44.0 and -78.0 <= lon <= -71.0:
            return lat, lon
    return None


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

    photos = [urllib.parse.unquote(src.rsplit("/", 1)[-1]) for src in _U26_IMG_RE.findall(markup)]
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
        photos=sorted(dict.fromkeys(photos)),
    )


def load_done(path: Path | None = None) -> dict[str, HikePage]:
    path = path or OUT_PATH
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    done = {}
    for row in document.get("pages", []):
        try:
            done[row["url"]] = HikePage(**row)
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
                "index": INDEX_URL,
                "one_time": True,
                "listed": len(links),
                "pages": [asdict(p) for p in pages],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main(limit: int | None, index_only: bool) -> int:
    made = session()

    print(f"Finding the most recent capture of {INDEX_URL} ...")
    capture = latest_capture(made, INDEX_URL)
    if capture is None:
        print("The archive would not serve the index. It was refusing this client earlier today;")
        print("wait longer rather than retrying in a loop - see THROTTLE_SECONDS.")
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

    print(f"\nFetching {len(todo)} write-ups at {THROTTLE_SECONDS:.0f}s apart - this is slow on purpose.")
    missed = 0
    for index, link in enumerate(todo, 1):
        found = latest_capture(made, link.replace("https://", "").replace("http://", ""))
        if found is None:
            missed += 1
            continue
        page_url, page_ts = found
        page_response = get(made, archived(page_url, page_ts))
        if page_response is None:
            missed += 1
            continue
        parsed = parse_page(page_response.text, link, page_ts)
        if parsed:
            pages.append(parsed)
        if index % 10 == 0:
            write_cache(pages, links)
            with_photo = sum(1 for p in pages if p.photos)
            print(f"  {index}/{len(todo)} ... {len(pages)} parsed, {with_photo} carry a photo")

    write_cache(pages, links)

    with_photo = [p for p in pages if p.photos]
    with_coords = [p for p in pages if p.lat is not None]
    print()
    print(f"  listed          {len(links)}")
    print(f"  recovered       {len(pages)}")
    print(f"  carry a photo   {len(with_photo)}")
    print(f"  carry a coord   {len(with_coords)}")
    print(f"  archive refused {missed}")
    print()
    print(f"  written to {OUT_PATH}")
    print("  Each photo filename here is a READ join to a hike, not a scored one.")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="Fetch only the first N write-ups.")
    parser.add_argument("--index-only", action="store_true", help="List what the index points at; fetch no pages.")
    args = parser.parse_args(argv)
    return main(args.limit, args.index_only)


if __name__ == "__main__":
    raise SystemExit(run())
