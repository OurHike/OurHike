"""Geofabrik's state extracts: where they are, which fourteen the A.T. crosses, and what one looks like.

The one home of these names, which export_basemap.py held until #1652 —
Download OSM's Geofabrik extracts at most once a month, into a private raw
bucket that outlives the 7-day Actions cache. They moved here because the
extract (extract/_geofabrik.py) lands the same fourteen files, and the
extract's job installs requirements-extract.txt alone, which holds none of
export_basemap.py's imports (shapely, pmtiles). export_basemap.py,
fetch_osm_water.py and fetch_trail_water.py import them from here, so the
basemap, both water scans and the extract read one list.

Nothing here imports anything beyond the standard library.
"""

from __future__ import annotations

from pathlib import Path

GEOFABRIK_BASE = "https://download.geofabrik.de/north-america/us"

# The fourteen states the AT corridor crosses - the default for --states, not
# a limit. Individual state extracts rather than us-northeast + us-south
# because the two region files together carry ~5.5 GB where these total
# ~3-4 GB (3.44 GB measured on build-basemap.yml run 30957719854,
# 2026-08-04, pipeline/BASEMAP.md), and every byte fetched here is also
# temp-disk the runner must hold.
AT_STATES = [
    "georgia",
    "north-carolina",
    "tennessee",
    "virginia",
    "west-virginia",
    "maryland",
    "pennsylvania",
    "new-jersey",
    "new-york",
    "connecticut",
    "massachusetts",
    "vermont",
    "new-hampshire",
    "maine",
]

#: The first block of every OSM PBF file is a BlobHeader whose type is this
#: string, a few bytes in (the OSM wiki's PBF format page: a 4-byte length,
#: then the header, whose field 1 is the type "OSMHeader"). An HTML error
#: page, an empty body or a truncated first block does not carry it.
PBF_HEADER_TYPE = b"OSMHeader"
#: How far into a file the header type is looked for: the length prefix is 4
#: bytes and the type field starts right after it, so 64 is generous.
PBF_HEAD_BYTES = 64


def extract_name(state: str) -> str:
    """The file name Geofabrik serves a state's extract under, and the one every fetcher here keeps it as."""
    return f"{state}-latest.osm.pbf"


def state_urls(states: list[str]) -> list[tuple[str, str]]:
    """(state, download URL) for each Geofabrik state extract."""
    return [(state, f"{GEOFABRIK_BASE}/{extract_name(state)}") for state in states]


def looks_like_pbf(path: Path) -> bool:
    """Whether a file opens the way every OSM PBF does: its first block's header names `OSMHeader`.

    A cheap check, not a parse: it refuses an error page or an empty body
    saved under a .pbf name, and says nothing about the file's later blocks.
    A body cut short is the sha256 and size checks' to catch.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(PBF_HEAD_BYTES)
    except OSError:
        return False
    return PBF_HEADER_TYPE in head[4:]
