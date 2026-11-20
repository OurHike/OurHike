"""Fetch the two atlas files the challenge map is drawn on (#1965).

Usage: python fetch_atlas_outlines.py

us-atlas's `states-10m.json` (the Census Bureau's state boundaries) and
world-atlas's `countries-50m.json` (Natural Earth's countries), each a
TopoJSON file at an exact npm version on jsDelivr, as sources.json's
`atlas_file` rows name them (lib/source_registry.py's ATLAS_FILE).
export_challenge_map.py reads them into challenge_map.json.

ONE DOWNLOAD PER VERSION, EVER. An npm version's files never change once
published, so a copy already on disk that parses as the topology its row
expects is the file the URL still serves, and is kept without asking the
network. Moving to a later edition is an edit to the row's URL, which lands
under a new name here because the version is in the file name - the old copy
is never mistaken for the new one.

A DOWNLOAD THAT IS NOT THE TOPOLOGY IS REFUSED, not kept. A CDN answering an
error page with a 200, or a truncated body, would otherwise be saved under a
`.json` name and read later as an empty map. The file is written beside its
destination first and moved into place only once it parses and carries the
object its row is read for.

robots.txt: unpkg.com and cdn.jsdelivr.net, read 2026-11-04 - unpkg's allows
every agent, and jsDelivr serves none (its root answers "Invalid URL"). Sent
under lib/user_agent.py's USER_AGENT.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from lib import fetch_receipts
from lib.atlas_sources import ATLAS_FILES
from lib.http_retry import download_with_retry
from lib.source_registry import atlas_files, load_registry
from lib.user_agent import USER_AGENT

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
FETCHER = "fetch_atlas_outlines"

#: An npm CDN URL pinned to an exact version: `<package>@<major>.<minor>.<patch>/`.
#: A range (`@3`) or a tag (`@latest`) can change under the same URL, which
#: is the one thing the keep-what-parses rule above cannot survive.
PINNED = re.compile(r"/npm/[a-z0-9-]+@\d+\.\d+\.\d+/")


class AtlasRefused(Exception):
    """A row or a download this fetcher will not stand behind."""


def topology_object(path: Path, object_name: str) -> dict | None:
    """The named object of the TopoJSON at `path`, or None when the file is
    absent, is not JSON, is not a Topology or does not carry that object."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict) or document.get("type") != "Topology":
        return None
    found = (document.get("objects") or {}).get(object_name)
    return found if isinstance(found, dict) and found.get("geometries") else None


def destination(key: str) -> tuple[Path, str]:
    """Where a row's file lands and the object it is read for."""
    if key not in ATLAS_FILES:
        raise AtlasRefused(f"{key}: an atlas_file row lib/atlas_sources.py does not name - add it there first")
    return ATLAS_FILES[key]


def fetch_one(row: dict, *, download=download_with_retry) -> tuple[Path, bool]:
    """Fetch one row's file unless a good copy is already here. Returns the
    path and whether the network was asked."""
    key, url = row["key"], row.get("url") or ""
    if not PINNED.search(url):
        raise AtlasRefused(f"{key}: {url!r} does not pin an exact package version, so a kept copy could be stale")
    path, object_name = destination(key)
    if topology_object(path, object_name) is not None:
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".download")
    try:
        download(url, partial, headers={"User-Agent": USER_AGENT}, label=key)
        if topology_object(partial, object_name) is None:
            raise AtlasRefused(f"{key}: {url} did not answer a TopoJSON topology carrying `{object_name}`")
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    return path, True


def main() -> list[Path]:
    rows = atlas_files(load_registry(SOURCES_PATH))
    if not rows:
        print("::error::sources.json registers no atlas_file row, so the challenge map has nothing to draw on.")
        sys.exit(1)
    fetched: list[Path] = []
    for row in rows:
        path, asked = fetch_one(row)
        print(f"{row['key']}: {'downloaded' if asked else 'kept'} {path.name} ({path.stat().st_size:,} bytes)")
        fetched.append(path)
    # After every file is in place, as fetch_receipts.record asks: a receipt
    # means "this finished".
    fetch_receipts.record(FETCHER, fetched)
    return fetched


if __name__ == "__main__":
    main()
