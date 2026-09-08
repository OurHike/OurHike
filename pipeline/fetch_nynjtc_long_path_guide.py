"""Fetch NYNJTC's Long Path End-to-End Section Guide into a cache and parse it.

    python fetch_nynjtc_long_path_guide.py

WHAT THIS IS FOR. The Long Path's lines already ship from NYNJTC's public
layer (sources.json's `nynjtc_long_path`). What that layer does not carry is
a single waypoint - no lot, no lean-to, no spring - and POI_COVERAGE_SURVEY.md
§6 found none anywhere on their ArcGIS org either. The section guide the
layer's own `GuideURL` field links to has all of them, mile by mile, in
prose. lib/nynjtc_long_path_guide.py is the reading; this is the fetch.

THE OUTPUT IS A CACHE, NOT AN ARTIFACT. It lands in `data/raw/`, which is
gitignored and is where CONTRIBUTING.md puts anything fetched:

    data/raw/nynjtc_long_path_guide/index.html          the guide's own table of contents
    data/raw/nynjtc_long_path_guide/lp-section-N.html   one page per section, as served
    data/raw/nynjtc_long_path_guide/sections.json       the parse, one object per section
    data/raw/nynjtc_long_path_guide/manifest.json       what was fetched, when, with what validators

Whether anything downstream may READ sections.json is sources.json's
question, not this script's - `nynjtc_long_path_guide` carries the answer
in `reaches_hikers`, and export_nearby_poi.py checks it. This fetches
regardless, the way fetch_club_pdfs.py does: a cache a person can review is
the first step of every licence conversation this project has had.

CHANGE-AWARE, like every fetcher here - but what "changed" means had to be
measured, because the obvious signal is wrong on these pages. Each page is
requested with If-None-Match / If-Modified-Since from this script's own
manifest, and a 304 keeps the cached page; NYNJTC serves neither validator
(read 2026-09-08: cache-control public max-age=300 and nothing else), so
that path is there for the day they do. The body hash is no use either: two
fetches of one page an hour apart differ in every WordPress gallery's
`galleryId`, a random token minted per render, so every page reads as
changed on every run. What is compared instead is the PARSE - the section's
facts as sections.json will hold them, hashed - which is the thing a
downstream reader would notice moving. That is recorded per page as
`content_sha256` beside the body's own `sha256`. Forty-one requests in the
steady state, throttled to one every half second, against a site that
publishes a section guide for people to read; naming the project in the
User-Agent is courtesy rather than necessity (NYNJTC does not refuse
scripted agents, verified for their alerts feed on 2026-08-27).

FAILING IS NOT THE SAME AS FINDING NOTHING. A run that cannot reach the
index, cannot reach a section the index links to, or parses a page it does
not recognise, leaves the previous cache exactly as it was and exits
non-zero - the strict-header posture of fetch_club_pdfs.py applied to a web
page. Pages are written only after every one of them has parsed, so a half
-updated cache is not a state this script can leave behind.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from lib.fetch_receipts import record
from lib.http_retry import request_with_retry
from lib.nynjtc_long_path_guide import INDEX_URL, SOURCE_KEY, parse_index, parse_section
from lib.source_registry import find_source, load_registry

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
OUT_DIR = ROOT / "data" / "raw" / "nynjtc_long_path_guide"
MANIFEST_PATH = OUT_DIR / "manifest.json"
SECTIONS_PATH = OUT_DIR / "sections.json"

USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"
THROTTLE_SECONDS = 0.5


def load_manifest(path: Path | None = None) -> dict:
    # Resolved at call time rather than bound as a default, so a test that
    # redirects MANIFEST_PATH is read from where it pointed.
    path = MANIFEST_PATH if path is None else path
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"pages": {}}


def fetch_page(session: requests.Session, url: str, previous: dict | None, out_path: Path) -> tuple[str, dict]:
    """One page's HTML and its manifest entry.

    A 304 reads the cached copy back rather than the wire, so the parse
    always sees the same bytes the cache holds. Whether the page CHANGED is
    not decided here - see main, which compares parses rather than bytes.
    """
    headers = {}
    if previous and out_path.exists():
        if previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        if previous.get("last_modified"):
            headers["If-Modified-Since"] = previous["last_modified"]
    response = request_with_retry(
        url,
        session=session,
        headers=headers,
        timeout=60,
        retryable_statuses=(429, 500, 502, 503, 504),
        label=url,
    )
    if response.status_code == 304:
        return out_path.read_text(encoding="utf-8"), dict(previous)

    body = response.text
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    entry = {
        "url": url,
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "sha256": digest,
        "bytes": len(body.encode("utf-8")),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return body, entry


def content_hash(section) -> str:
    """The section's facts, hashed - the change signal (see the module docstring)."""
    return hashlib.sha256(json.dumps(section.to_dict(), sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


def main() -> None:
    registry = load_registry(SOURCES_PATH)
    source = find_source(registry, SOURCE_KEY)
    if source is None:
        print(f"{SOURCE_KEY} is not registered in sources.json - nothing to fetch", file=sys.stderr)
        sys.exit(1)
    index_url = source.get("url", INDEX_URL)

    previous = load_manifest()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    index_path = OUT_DIR / "index.html"
    index_html, index_entry = fetch_page(session, index_url, previous["pages"].get("index"), index_path)
    pages = parse_index(index_html)
    print(f"index: {len(pages)} section pages linked")

    fetched: dict[int, tuple[str, dict]] = {}
    for number, url in pages:
        time.sleep(THROTTLE_SECONDS)
        key = f"lp-section-{number}"
        fetched[number] = fetch_page(session, url, previous["pages"].get(key), OUT_DIR / f"{key}.html")

    sections = []
    changed = []
    for number, url in pages:
        html, entry = fetched[number]
        # A page that no longer parses stops the run here, before anything is
        # written - the previous cache and its sections.json stay as they were.
        section = parse_section(html, url, expected_number=number)
        sections.append(section)
        entry["content_sha256"] = content_hash(section)
        before = (previous["pages"].get(f"lp-section-{number}") or {}).get("content_sha256")
        if entry["content_sha256"] != before:
            changed.append(number)

    index_path.write_text(index_html, encoding="utf-8")
    manifest = {
        "source": SOURCE_KEY,
        "index_url": index_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pages": {"index": index_entry, **{f"lp-section-{n}": entry for n, (_, entry) in fetched.items()}},
    }
    for number, (html, _) in fetched.items():
        (OUT_DIR / f"lp-section-{number}.html").write_text(html, encoding="utf-8")
    SECTIONS_PATH.write_text(json.dumps([s.to_dict() for s in sections], indent=1, ensure_ascii=False), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    entries = sum(len(s.parking) + len(s.camping) + len(s.description) for s in sections)
    located = sum(1 for s in sections for e in s.parking + s.camping + s.description if e.lat is not None)
    print(f"{len(sections)} sections parsed: {entries:,} mile-marked entries, {located} with NYNJTC's own coordinates")
    if previous["pages"]:
        print(f"{len(changed)} section(s) whose parsed content changed since the last run" + (f": {changed}" if changed else ""))
    else:
        print("first fetch")
    print(f"-> {SECTIONS_PATH}")
    if not source.get("reaches_hikers"):
        print(
            f"   {SOURCE_KEY} carries reaches_hikers: false - export_nearby_poi.py will not publish from this cache (see sources.json's nynjtc_guide_licence)"
        )

    record("fetch_nynjtc_long_path_guide", [SECTIONS_PATH, MANIFEST_PATH], root=ROOT)


if __name__ == "__main__":
    main()
