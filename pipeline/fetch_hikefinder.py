"""Read the whole NYNJTC hike list off the Hike Finder export into a cache,
with the published GPX track for every hike that has one (#1427).

    python fetch_hikefinder.py                 the listing, every hike page, every GPX
    python fetch_hikefinder.py --refetch-gpx   re-download tracks already cached

WHAT THIS IS FOR, AND WHAT IT REPLACES. heardimmunity.org/hikefinder is the
maintainer's full export of NYNJTC's hike write-ups: 385 pages against the 20
that `fetch_nynjtc_hikes.py` could reach on nynjtc.org, where the other 39 of
59 sit behind NYNJTC's own password. The instruction of 2026-09-15 was to load
the export and stop scraping the site, so this fetcher is the road these hikes
arrive by and that one is retired. `lib/hikefinder.py` is the reading; this is
the fetch.

THE OUTPUT IS A CACHE, NOT AN ARTIFACT. It lands in `data/raw/`, which is
gitignored and is where CONTRIBUTING.md puts anything fetched:

    data/raw/hikefinder.json              every hike, parsed, with what it is missing
    data/raw/hikefinder_gpx/<id>.gpx      the published track, verbatim

THE GPX IS KEPT AS BYTES, not as parsed points, and that is deliberate. It is
somebody's survey of ground they walked and the most authoritative thing in
this import; a cache holding the file itself can be re-read by a later parse
that wants something this one did not keep, and can be checked against the
export byte for byte. `lib/hikefinder.py`'s `parse_gpx` reads it at the point
of use.

BEING POLITE TO SOMEBODY ELSE'S SERVER. One request for the listing, one per
hike page, and one per track the cache does not already hold - 385 + 113 on a
cold run, 385 on a warm one, throttled to two a second and naming the project
in the User-Agent. A track is downloaded ONCE: the export publishes no
per-hike validator, so a cached file is carried forward unless `--refetch-gpx`
says otherwise, and the page's own `Last Updated` is what says the write-up
moved.

NO FRESHNESS MARKER, and check_freshness.py is deliberately not taught one:
measured 2026-09-15, `hikes.php` serves neither an ETag nor a Last-Modified
and the export publishes no feed. What moves is each page's `Last Updated`
field, which this fetch compares against its own previous cache and reports -
the shape `fetch_nynjtc_long_path_guide.py` settled on for pages that serve no
validator.

FAILING IS NOT THE SAME AS FINDING NOTHING - `fetch_atc_updates.py`'s rule,
and it transfers unchanged. A run that cannot reach the export, reads a
listing it does not recognise, or parses no hike at all leaves the previous
cache in place and exits non-zero. The cache is written atomically at the end
for that reason. A single page or track that fails is a line in the log and a
hike recorded as incomplete - never a failed run, because 384 hikes cached is
better than 385 refused, and the cache says which one is missing.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

from lib.fetch_receipts import record
from lib.hikefinder import (
    DETAIL_PATH,
    GPX_PATH,
    LISTING_PATH,
    SOURCE_KEY,
    as_cache_entry,
    listing_count,
    listing_ids,
    parse_gpx,
    parse_hike,
)
from lib.http_retry import request_with_retry
from lib.source_registry import find_source, load_registry
from lib.user_agent import USER_AGENT

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
CACHE_PATH = RAW_DIR / "hikefinder.json"
GPX_DIR = RAW_DIR / "hikefinder_gpx"

#: Half a second between requests - the pace fetch_nynjtc_hikes.py took
#: against the club's own host, kept for a smaller one.
THROTTLE_SECONDS = 0.5
TIMEOUT = 60

#: How far the listing's own count may sit from the number of linked ids
#: before the run is refused. ZERO: the two are the same page describing
#: itself, and a disagreement means the listing paginated or a row lost its
#: link - either way the export is no longer the shape this fetcher reads,
#: and caching the shorter answer would report a shrunken export as complete.
COUNT_TOLERANCE = 0


def session() -> requests.Session:
    made = requests.Session()
    made.headers["User-Agent"] = USER_AGENT
    return made


def load_previous(path: Path | None = None) -> dict:
    """The last run's hikes, keyed by id as a string, or {} on the first run
    or on a cache this build cannot read - a cache is a convenience, and a
    corrupt one costs a re-fetch rather than a run."""
    path = path or CACHE_PATH
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    hikes = document.get("hikes")
    return hikes if isinstance(hikes, dict) else {}


def fetch_text(http, url: str) -> str:
    return request_with_retry(url, session=http, timeout=TIMEOUT, label="hikefinder", throttle_seconds=THROTTLE_SECONDS).text


def store_gpx(http, base: str, hike_id: int, refetch: bool) -> tuple[str | None, str]:
    """Download one hike's track into the cache; the relative path and one
    word for the log: `carried`, `fetched`, `unreadable` or `failed`.

    A file that downloads but holds no `trkpt` is `unreadable` and is NOT
    written: a zero-point track saved under a name promising a route is worse
    than no file, because every later stage would have to re-discover that it
    is empty.
    """
    path = GPX_DIR / f"{hike_id}.gpx"
    if path.exists() and path.stat().st_size > 0 and not refetch:
        return path.name, "carried"
    url = urljoin(base, GPX_PATH.format(id=hike_id))
    try:
        response = request_with_retry(
            url, session=http, timeout=TIMEOUT, label="hikefinder/gpx", throttle_seconds=THROTTLE_SECONDS
        )
    except Exception as error:  # noqa: BLE001 - one track must not end the run
        print(f"    gpx failed for {hike_id}: {type(error).__name__}: {error}")
        return None, "failed"
    text = response.text
    if parse_gpx(text) is None:
        print(f"    gpx for {hike_id} parsed to no track point")
        return None, "unreadable"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)
    return path.name, "fetched"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    refetch = "--refetch-gpx" in argv

    registry = load_registry(SOURCES_PATH)
    source = find_source(registry, SOURCE_KEY)
    if source is None:
        print(f"{SOURCE_KEY} is not registered in sources.json - nothing to fetch", file=sys.stderr)
        return 1
    base = source["url"]
    if not base.endswith("/"):
        base += "/"

    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    http = session()

    listing = fetch_text(http, urljoin(base, LISTING_PATH))
    ids = listing_ids(listing)
    if not ids:
        print("The listing linked no hike at all, which means the parse broke rather than that there are none.")
        return 1
    stated = listing_count(listing)
    if stated is not None and abs(stated - len(ids)) > COUNT_TOLERANCE:
        print(
            f"The listing says {stated} hikes and links {len(ids)} - see COUNT_TOLERANCE. "
            "Leaving the previous cache in place; the export's shape has changed."
        )
        return 1

    previous = load_previous()
    hikes: dict[str, dict] = {}
    gpx_outcomes: dict[str, int] = {}
    unreadable: list[int] = []
    changed: list[str] = []

    for hike_id in ids:
        url = urljoin(base, DETAIL_PATH.format(id=hike_id))
        try:
            page = fetch_text(http, url)
        except Exception as error:  # noqa: BLE001 - one page must not end the run
            print(f"    page failed for {hike_id}: {type(error).__name__}: {error}")
            unreadable.append(hike_id)
            continue
        hike = parse_hike(page, hike_id, url)
        if hike is None:
            unreadable.append(hike_id)
            continue
        entry = as_cache_entry(hike, stamp)
        if hike.has_published_route:
            name, outcome = store_gpx(http, base, hike_id, refetch)
            gpx_outcomes[outcome] = gpx_outcomes.get(outcome, 0) + 1
            entry["gpx_file"] = name
        else:
            entry["gpx_file"] = None
        hikes[str(hike_id)] = entry
        prior = previous.get(str(hike_id))
        if prior is None or prior.get("updated_on") != entry["updated_on"] or prior.get("published_on") != entry["published_on"]:
            changed.append(str(hike_id))

    if not hikes:
        print(f"{len(ids)} hikes listed and none parsed - the export's shape has changed, not its contents.")
        return 1

    document = {
        "source": SOURCE_KEY,
        "fetched_at": stamp,
        "base_url": base,
        "listed": len(ids),
        "stated_total": stated,
        "parsed": len(hikes),
        "unreadable": unreadable,
        "with_published_route": sum(1 for entry in hikes.values() if entry["has_published_route"]),
        "hikes": hikes,
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, CACHE_PATH)

    print(
        f"{len(ids)} hikes listed, {len(hikes)} parsed, {len(unreadable)} unreadable{': ' + ', '.join(map(str, unreadable[:10])) if unreadable else ''}"
    )
    print(
        f"{document['with_published_route']} carry a published GPX route; {len(hikes) - document['with_published_route']} carry only a start and a description"
    )
    if gpx_outcomes:
        print("tracks: " + ", ".join(f"{count} {word}" for word, count in sorted(gpx_outcomes.items())))
    if previous:
        print(f"{len(changed)} hike(s) new or revised since the last run")
    else:
        print("first fetch")
    problems: dict[str, int] = {}
    for entry in hikes.values():
        for problem in entry["problems"]:
            problems[problem] = problems.get(problem, 0) + 1
    if problems:
        print("what the export does not carry:")
        for problem, count in sorted(problems.items(), key=lambda pair: -pair[1]):
            print(f"  {count:4}  {problem}")
    print(f"-> {CACHE_PATH}")
    if not source.get("reaches_hikers"):
        print(f"   {SOURCE_KEY} carries reaches_hikers: false - export_suggested_hikes.py will not publish from this cache")

    record("fetch_hikefinder", [CACHE_PATH], root=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
