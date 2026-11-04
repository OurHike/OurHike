"""The two atlas files the challenge map is drawn on (#1965): their registry
keys, where fetch_atlas_outlines.py lands them, and the object each one is
read for.

One home for the keys, because three modules read them - the fetcher that
downloads the files, export_challenge_map.py that reads them, and
export_sources.py, which counts a `static_file` row on the exporters' path
only when its key is one an exporter declares (lib/source_registry.py's
EXPORTER_ONE_ROW_KINDS). A key spelled twice would let a steward drop off the
sources screen while their outlines are on every poster.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "atlas"

#: sources.json's key for us-atlas's `states-10m.json`: the US states as
#: TopoJSON, from the Census Bureau's cartographic boundary files.
US_ATLAS_KEY = "us_atlas_states"
#: sources.json's key for world-atlas's `countries-50m.json`: the countries
#: as TopoJSON, from Natural Earth. Read for Canada alone (the ground north
#: of Maine and New York), at 1:50m because 1:110m draws the St. Lawrence
#: and the Great Lakes' north shores as a handful of straight lines.
WORLD_ATLAS_KEY = "world_atlas_countries"

ATLAS_SOURCE_KEYS = frozenset({US_ATLAS_KEY, WORLD_ATLAS_KEY})

#: Where each file lands, and the TopoJSON object it must carry to count as
#: fetched - the check fetch_atlas_outlines.py makes before it keeps a file,
#: because an HTML error page saved under a `.json` name is the failure a
#: download-whole fetcher is prone to.
ATLAS_FILES: dict[str, tuple[Path, str]] = {
    US_ATLAS_KEY: (RAW_DIR / "us-atlas-states-10m.json", "states"),
    WORLD_ATLAS_KEY: (RAW_DIR / "world-atlas-countries-50m.json", "countries"),
}
