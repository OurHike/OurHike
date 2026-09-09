"""Fetch ATC's centerline on its own, in the reduced shape the drought clip needs.

Usage: python fetch_centerline.py

WHY THIS IS NOT `fetch_all.py`. That script pulls all twelve ATC feature
layers with every attribute, which is right for the vector publish and far
more than `publish-conditions.yml` wants. The hourly conditions bake needs
the centerline and nothing else, and it needs it only as geometry: it buffers
the line into a corridor and clips this week's drought polygons against it
(`export_drought.py`), so every attribute it would otherwise download is
thrown away unread. `outFields=''` and `geometryPrecision=5` are that,
stated - about 1 m of coordinate precision, against a corridor buffer
`export_drought.py` measures in tens of kilometres.

WHY IT IS A SCRIPT AND NOT FOUR LINES OF YAML (#1295). It was the latter
until now: an inline `python -c` heredoc in `publish-conditions.yml` that
re-implemented `lib/arcgis.py`'s offset paging from scratch, on
`urllib.request.urlopen` with no retry. Three things followed, and the last
is the one that matters.

  - Nothing could test it. Python inside a YAML string is unreachable from
    `pipeline/tests/`, so the one copy of this loop that had no tests was
    the copy fetching the trail itself.
  - Nothing could see it. `scripts/pipeline_scopes.py` derives a workflow's
    scope from the `<name>.py` files it mentions, so a heredoc made this
    fetch invisible to the tooling that decides which publishing paths a
    change stales.
  - It carried a bug `lib/arcgis.py` had already fixed. The heredoc stopped
    paging on any page shorter than the requested size unless the response
    also set `exceededTransferLimit`. `lib/arcgis.py` stopped doing that
    deliberately - `tests/test_lib_arcgis.py` holds two regression tests for
    it, one simulating exactly the case that breaks it: a server whose own
    `maxRecordCount` sits below the size asked for, so every page comes back
    short while features remain. The centerline is 3,025 features
    (README.md, measured); asked for in pages of 2,000 it takes two, and a
    service capping below that would have ended the loop early with a
    partial trail and no error.

    NOT claimed: that this was truncating in production. It rested on
    `exceededTransferLimit` being present and honest in a `f=geojson`
    response, which it may well have been every time. What is claimed is
    that the shared loop does not need that to be true, and that no test
    anywhere established it was.
"""

import json
import sys
from pathlib import Path

from lib.arcgis import fetch_layer_geojson
from lib.source_registry import find_source, load_registry

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
OUT_PATH = ROOT / "data" / "raw" / "centerline.geojson"

SOURCE_KEY = "centerline"

# Geometry only. Every ATC attribute on this layer - Trail_Club, Acronym, the
# rest - is read by `export_club_sections.py` off the copy `fetch_all.py`
# pulls, never off this one.
OUT_FIELDS = ""

# ~1 m at these latitudes. `export_drought.py` simplifies the line by about
# 110 m before buffering it, so five decimal places is already far finer than
# anything downstream can distinguish.
GEOMETRY_PRECISION = 5

# Bigger pages than lib/arcgis.PAGE_SIZE's 1000, because this is one layer of
# ~3,025 geometry-only features and the round trips are the cost. The loop is
# correct at any page size - it stops on an empty page, not a short one - so
# this is a speed choice and nothing rests on it.
PAGE_SIZE = 2000


def main() -> int:
    registry = load_registry(SOURCES_PATH)
    source = find_source(registry, SOURCE_KEY)
    if source is None:
        print(f"No source registered under {SOURCE_KEY!r} in {SOURCES_PATH}.", file=sys.stderr)
        return 1

    collection = fetch_layer_geojson(
        source["url"],
        out_fields=OUT_FIELDS,
        geometry_precision=GEOMETRY_PRECISION,
        page_size=PAGE_SIZE,
    )
    count = len(collection["features"])

    # A centerline that came back empty is not a trail with no segments; it is
    # a query that failed while answering 200, which is a shape ArcGIS is known
    # to produce (fetch_all.py's docstring records it). Clipping drought bands
    # against nothing would draw bands nowhere and look like a quiet week.
    #
    # THE CHECK IS BEFORE THE WRITE, not after, and that ordering is the whole
    # value of it. `fetch_layer_to_file` would have put the empty collection on
    # disk and left this function to complain about a file that already exists
    # - and the workflow's own cold-cache test is `[ ! -s centerline.geojson ]`,
    # so an empty-but-present file is one the next run treats as a cache hit and
    # never refetches. Refusing has to mean nothing was written.
    if count == 0:
        print(
            f"{SOURCE_KEY} came back with 0 features - refusing to write an empty centerline.",
            file=sys.stderr,
        )
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(collection))
    print(f"Fetched {count} centerline features -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
