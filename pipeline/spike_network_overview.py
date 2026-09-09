"""Measure what a corridor-view overview of the whole trail network would weigh.

The maintainer's ask, 2026-08-27: *"The opening map probably just needs to be
all the trails that we have mapped. Not including the POIs... and reduce the
amount of data needed to display the map."* The display half of that is a
mockup (`features/mockups/opening-map.html`); this is the measuring half: if
`export_nearby_trails.py` published an overview the way `export_trails.py`'s
`write_overview` already publishes the A.T.'s (#869), what would it cost a
phone, and what would it carry?

    cd pipeline && python spike_network_overview.py --base https://data.ourhike.org

Every number in that mockup's data callouts comes from this script, so a reader
who doubts one can re-run it rather than re-derive it by hand.

WHAT IT MEASURES, and against what. The subject is the PUBLISHED
`nearby_trails.geojson` - the bytes phones actually hold - not a local export,
so the answer moves when a publish does and never when a working tree does.
The method is `write_overview`'s own, imported rather than copied so the two
cannot drift: EPSG:5070, Douglas-Peucker at `OVERVIEW_SIMPLIFY_TOLERANCE_M`
(100 m), coordinates rounded to `OVERVIEW_COORDINATE_DECIMALS` (4), features
merged into one MultiLineString per group.

ONE DECISION IS THIS SCRIPT'S RATHER THAN write_overview's: the merge key is
(source, blaze_color, trail_status), where the A.T.'s overview needs no key at
all (one source, no status column). `source` and `blaze_color` are the two
properties the client's line expressions read (map/style.ts), so keeping them
is what lets an overview draw through the same paint as the real lines.
`trail_status` is the safety column - 224 of 21,805 features read `closed`
(measured 2026-08-27, the #964-derived areas among them) - and folding closed
ground into an `open` feature would draw it open-looking below the seam, which
is the display outrunning its source. Measured cost of keeping it: 25 -> 31
features, +328 gzipped bytes.

Measured 2026-08-27 against the live bucket (nearby_trails.geojson at
7,703,741 wire bytes, 21,805 features):

    features                31  (source x blaze x status)
    coordinates        480,115 -> 57,226
    raw bytes        1,125,263
    gzipped (-9)       255,263   . the published A.T. overview is 51,068
    line-miles         7,669.7   . DEC 4,272.4 / OPRHP 2,748.4 / Long Path
                                   415.2 / Highlands 167.4 / Mohonk 66.4
    closed              48.4 mi in 224 features
    bbox            W -79.59 S 40.50 E -71.86 N 45.01 - inside CORRIDOR_BOUNDS
                    [[-84.73, 34.2], [-68.3, 46.34]], so the opening camera
                    already frames every mapped trail

Line-miles are EPSG:5070 lengths of what the artifact holds - line on the map,
not deduplicated trail, so braided or doubly-digitized ground counts as drawn.

Downloads are cached under data/spike/network_overview/ and reused; --refetch
forces current bytes. The built overview is written beside them for looking
at, never for publishing - if the maintainer wants this shipped, it belongs in
export_nearby_trails.py where the manifest, the hash and verify_release can
hold it (the pattern #869 set).
"""

import argparse
import gzip
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import requests
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

from export_trails import (
    _TO_GEOGRAPHIC,
    _TO_METRIC,
    OVERVIEW_COORDINATE_DECIMALS,
    OVERVIEW_SIMPLIFY_TOLERANCE_M,
)

SPIKE_DIR = Path(__file__).parent / "data" / "spike" / "network_overview"
NEARBY_KEY = "nearby_trails.geojson"
AT_OVERVIEW_KEY = "trails_overview.geojson"
METERS_PER_MILE = 1609.344

# App.tsx's opening camera, for the bbox verdict below. Hand-copied rather than
# imported because the client constant lives in TypeScript; style.test.ts-style
# drift is accepted here since a spike re-run re-checks it.
CORRIDOR_BOUNDS = ((-84.73, 34.2), (-68.3, 46.34))


def fetch(base: str, key: str, refetch: bool) -> bytes:
    """The published artifact's decoded bytes, from the spike cache or the bucket."""
    SPIKE_DIR.mkdir(parents=True, exist_ok=True)
    cached = SPIKE_DIR / key
    if cached.exists() and not refetch:
        return cached.read_bytes()
    response = requests.get(f"{base.rstrip('/')}/{key}", timeout=120)
    response.raise_for_status()
    cached.write_bytes(response.content)
    return response.content


def component_lines(geom):
    return [geom] if geom.geom_type == "LineString" else list(geom.geoms)


def build_overview(features: list[dict]) -> tuple[dict, dict]:
    """The overview FeatureCollection plus the measurements main() prints."""
    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    miles_by_source: dict[str, float] = defaultdict(float)
    closed_miles = 0.0
    closed_features = 0
    coords_before = 0
    coords_after = 0
    bbox = [180.0, 90.0, -180.0, -90.0]

    for feature in features:
        props = feature.get("properties") or {}
        source = str(props.get("source", ""))
        status = str(props.get("trail_status", "") or "")
        geom = shape(feature["geometry"])
        projected = shapely_transform(_TO_METRIC, geom)
        miles_by_source[source] += projected.length / METERS_PER_MILE
        if status.lower() == "closed":
            closed_miles += projected.length / METERS_PER_MILE
            closed_features += 1
        simplified = shapely_transform(
            _TO_GEOGRAPHIC,
            projected.simplify(OVERVIEW_SIMPLIFY_TOLERANCE_M, preserve_topology=False),
        )
        coords_before += sum(len(line.coords) for line in component_lines(geom))
        key = (source, str(props.get("blaze_color", "")), status)
        for line in component_lines(simplified):
            coords_after += len(line.coords)
            rounded = [[round(x, OVERVIEW_COORDINATE_DECIMALS), round(y, OVERVIEW_COORDINATE_DECIMALS)] for x, y in line.coords]
            groups[key].append(rounded)
            for x, y in line.coords:
                bbox[0] = min(bbox[0], x)
                bbox[1] = min(bbox[1], y)
                bbox[2] = max(bbox[2], x)
                bbox[3] = max(bbox[3], y)

    body = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"source": source, "blaze_color": blaze, "trail_status": status},
                "geometry": {"type": "MultiLineString", "coordinates": lines},
            }
            for (source, blaze, status), lines in sorted(groups.items())
        ],
    }
    stats = {
        "miles_by_source": dict(miles_by_source),
        "closed_miles": closed_miles,
        "closed_features": closed_features,
        "coords_before": coords_before,
        "coords_after": coords_after,
        "bbox": bbox,
    }
    return body, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", metavar="URL", help="Public bucket base. Defaults to $DATA_BASE_URL.")
    parser.add_argument("--refetch", action="store_true", help="Refetch the artifacts instead of reusing the cache.")
    args = parser.parse_args()

    base = args.base or os.environ.get("DATA_BASE_URL")
    if not base:
        print("No bucket to measure against: pass --base or set DATA_BASE_URL.", file=sys.stderr)
        return 2

    nearby_bytes = fetch(base, NEARBY_KEY, args.refetch)
    features = json.loads(nearby_bytes)["features"]
    print(f"{NEARBY_KEY}: {len(features):,} features, {len(nearby_bytes):,} bytes decoded")

    body, stats = build_overview(features)
    raw = json.dumps(body, separators=(",", ":")).encode()
    gz = len(gzip.compress(raw, 9))
    out = SPIKE_DIR / "network_overview.geojson"
    out.write_bytes(raw)

    print(f"overview: {len(body['features'])} features (source x blaze x status)")
    print(f"  coordinates {stats['coords_before']:,} -> {stats['coords_after']:,}")
    print(f"  {len(raw):,} bytes raw, {gz:,} gzipped (-9)  -> {out}")
    try:
        at_bytes = fetch(base, AT_OVERVIEW_KEY, args.refetch)
        at_gz = len(gzip.compress(at_bytes, 9))
        print(f"  beside the published A.T. overview: {at_gz:,} gzipped locally, ~{gz + at_gz:,} for the pair")
    except (OSError, requests.RequestException) as error:
        print(f"  ({AT_OVERVIEW_KEY} not fetched: {error} - the pair figure needs it)")

    west, south, east, north = stats["bbox"]
    (cw, cs), (ce, cn) = CORRIDOR_BOUNDS
    inside = cw <= west and cs <= south and east <= ce and north <= cn
    verdict = "inside" if inside else "OUTSIDE - the opening camera would crop mapped trail"
    print(f"  bbox W {west:.2f} S {south:.2f} E {east:.2f} N {north:.2f} - {verdict} CORRIDOR_BOUNDS")

    print("  line-miles by source (EPSG:5070 length of what the artifact holds):")
    total = 0.0
    for source, miles in sorted(stats["miles_by_source"].items(), key=lambda kv: -kv[1]):
        print(f"    {source:26s} {miles:10,.1f}")
        total += miles
    print(f"    {'TOTAL':26s} {total:10,.1f}")
    print(f"  closed: {stats['closed_miles']:,.1f} line-miles in {stats['closed_features']} features")
    return 0


if __name__ == "__main__":
    sys.exit(main())
