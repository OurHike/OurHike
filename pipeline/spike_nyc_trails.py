"""Harriman's crossing trails next to the AT — what a network breaks (#771).

Everything this app ships assumes one linear trail. Harriman–Bear Mountain is
~1,000 OPRHP segments of crossing named trails with the AT and the Long Path
running through the middle, and this spike puts the real data on the table and
measures which assumptions bend and which break. The numbers land in #771 and
feed features/NEARBY_TRAILS.md (#772) and the offline-unit decision (#552).

THIS IS A SPIKE. The assembly below is throwaway; what should survive is the
SHAPE of the answers — how cleanly (Facility, Name) partitions into walkable
chains, how dense the crossings are, and how far the AT ever is from somebody
else's trail — not this code. Pure helpers are kept honest by
tests/test_spike_nyc_trails.py; the measurement half runs against real fetched
data and network-cached extracts under data/spike/nyc_trails/.

Inputs:
  - data/raw/external/oprhp_trails.geojson  (fetch_external_layers.py, #769)
  - the ATC centerline's Harriman window, fetched once from the URL
    sources.json registers and cached (the full corridor file is not needed)
  - NYNJTC's public Long Path service (NYC_SOURCE_SURVEY.md §4), cached

**Hiking trails only — maintainer decision, 2026-08-18** ("Only keep hiking
trails for now… It's OurHike, not OurBike"): the spike keeps segments whose
`Foot` flag allows foot travel and drops the rest. The other use columns the
OPRHP layer carries, listed here as the decision asked, and likely never used:
`Bike`, `Horse`, `XC` (cross-country ski), `SS` (snowshoe), `Snowmb`
(snowmobile). DEC's layer has the same split one service over
(NYC_SOURCE_SURVEY.md §3: XC 4,511 / mountain bike 2,478 / snowmobile 2,365 /
horse 1,263 / ATV+MOTORV flags), and NJ's layers carry the same flags —
whatever future revisits this does it per-source, not by widening this filter.

Measured domains behind the filters (2026-08-18, statewide, 16,641 rows):
  Foot:    {'Y': 16441, 'N': 200}         — a clean two-value domain
  Public_: {'Y': 16641}                   — OPRHP pre-filters to public trails
  Status:  {'Open': 16473, 'Closed': 125, None: 21, 'Proposed': 19,
            'Unknown': 3}
Status handling — maintainer decision, 2026-08-18, taken with these numbers
in front of them: `Open` ships as trail, **`Closed` ships drawn as closed**
(the barred treatment, so someone standing at the trailhead with an old paper
map is told, rather than the trail silently missing), `Proposed` is dropped
(it does not exist on the ground), and None/Unknown are dropped with their
count reported — omit rather than guess.

Two more maintainer decisions taken during this spike, recorded where the
code embodies them (both 2026-08-18, both also on #772):
  - **The route owner's line always renders.** Where two orgs draw the same
    trail — measured below: ATC's AT vs OPRHP's copy, NYNJTC's Long Path vs
    OPRHP's — the org that owns the route supplies the centerline, and the
    landowner's copy is suppressed as a duplicate. The divergence numbers
    this spike prints are the evidence that the copies are not the same line.
  - POIs dedupe into shared cross-org records, attach to the chosen route,
    and the selected org wins the display — #772's comment thread holds the
    full wording; #780 researches what "the org" even is on jointly-owned
    routes.
"""

import gzip
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import requests
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, shape
from shapely.ops import linemerge, unary_union

ROOT = Path(__file__).parent
OPRHP_TRAILS = ROOT / "data" / "raw" / "external" / "oprhp_trails.geojson"
OPRHP_PARKS = ROOT / "data" / "raw" / "external" / "oprhp_park_polygons.geojson"
SPIKE_DIR = ROOT / "data" / "spike" / "nyc_trails"
SHIPPED_TRAILS = ROOT / "data" / "processed" / "trails.geojson"

AREA_FACILITIES = ("Harriman State Park", "Bear Mountain State Park")

# The Harriman–Bear Mountain window, generous enough to catch the AT's whole
# crossing of both parks (lon/lat, W S E N).
AREA_BBOX = (-74.25, 41.15, -73.95, 41.40)

# Where the two overlay lines come from. The ATC centerline URL is read from
# sources.json (the registry is the one home for it); the Long Path service is
# NYC_SOURCE_SURVEY.md §4's — public, season-stable URL, review-only licence.
LONG_PATH_URL = "https://services7.arcgis.com/G1WTEJ6UVRUTvh9C/arcgis/rest/services/Long_Path_2023/FeatureServer/0"

# Harriman sits in UTM 18N; distances below are meters in this projection.
WGS84_TO_UTM18 = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True)

METERS_PER_MILE = 1609.344

# Sampling stride for line-to-line offset measurements. 50 m ≈ 2–3 GPS error
# radii under canopy — fine enough that a real divergence cannot hide between
# samples, coarse enough that the whole AT crossing costs ~600 samples.
SAMPLE_STRIDE_M = 50.0

# Endpoint coordinates are rounded to 5 decimal places (~1.1 m) before
# junction matching, so two segments digitised to meet actually match.
JUNCTION_ROUND = 5


# --- Pure helpers (tested) --------------------------------------------------


def keep_hiking(features: list[dict]) -> tuple[list[dict], Counter]:
    """The maintainer's 2026-08-18 hiking-only filter, plus their Status
    decision (module docstring): Open and Closed both ship — Closed so the
    map can draw it barred — while Proposed and blank/Unknown drop. Returns
    (kept, dropped_counter) so the run reports what it excluded rather than
    silently shrinking."""
    kept = []
    dropped: Counter = Counter()
    for feature in features:
        props = feature.get("properties") or {}
        if props.get("Foot") != "Y":
            dropped["not foot travel (Foot != 'Y')"] += 1
            continue
        status = props.get("Status")
        if status not in ("Open", "Closed"):
            dropped[f"Status: {status}"] += 1
            continue
        kept.append(feature)
    return kept, dropped


def named_groups(features: list[dict]) -> dict[tuple[str, str], list]:
    """Segments grouped by (Facility, Name), geometry as shapely, for the
    chain-assembly question. Blank and missing names group under '' so the
    unnamed share is measured rather than vanishing."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for feature in features:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry")
        if not geometry:
            continue
        name = (props.get("Name") or "").strip()
        facility = (props.get("Facility") or "").strip()
        groups[(facility, name)].append(shape(geometry))
    return dict(groups)


def chain_report(groups: dict[tuple[str, str], list]) -> dict:
    """How cleanly each named trail merges into walkable chains.

    A trail whose segments linemerge into ONE LineString is a chosen-trail
    centerline the app's model can take today; every extra part is a gap, a
    fork, or a discontiguous reuse of the name — the thing #772 has to design
    for and #161's merged-chains work meets from the other side."""
    named = {key: geoms for key, geoms in groups.items() if key[1]}
    parts_per_trail = {}
    for key, geoms in named.items():
        merged = linemerge(
            MultiLineString([g for geom in geoms for g in (geom.geoms if isinstance(geom, MultiLineString) else [geom])])
        )
        parts_per_trail[key] = 1 if isinstance(merged, LineString) else len(merged.geoms)
    clean = sum(1 for n in parts_per_trail.values() if n == 1)
    return {
        "named_trails": len(named),
        "single_chain": clean,
        "multi_part": {
            f"{fac} / {name}": n for (fac, name), n in sorted(parts_per_trail.items(), key=lambda kv: -kv[1]) if n > 1
        },
        "unnamed_segments": sum(len(g) for key, g in groups.items() if not key[1]),
    }


def junction_count(features: list[dict]) -> int:
    """Points where two DIFFERENT named trails share an endpoint — the
    network's crossing density, counted from endpoints because that is how
    this layer digitises junctions (segments break where trails meet)."""
    at_point: dict[tuple, set] = defaultdict(set)
    for feature in features:
        props = feature.get("properties") or {}
        name = (props.get("Name") or "").strip()
        geometry = feature.get("geometry")
        if not geometry or not name:
            continue
        geom = shape(geometry)
        lines = geom.geoms if isinstance(geom, MultiLineString) else [geom]
        for line in lines:
            for pt in (line.coords[0], line.coords[-1]):
                at_point[(round(pt[0], JUNCTION_ROUND), round(pt[1], JUNCTION_ROUND))].add(name)
    return sum(1 for names in at_point.values() if len(names) >= 2)


def blaze_report(features: list[dict], client_colors: set[str]) -> dict:
    """OPRHP's blaze columns against the palette the client actually paints
    (client/src/lib/blaze.ts) — the TRAIL_BLAZE_COLORS.md extension question,
    measured. `Map_Blaze` is compared where both are present."""
    values = Counter((f.get("properties") or {}).get("Blaze") for f in features)
    disagree = sum(
        1
        for f in features
        if (p := f.get("properties") or {}).get("Blaze") and p.get("Map_Blaze") and p["Blaze"] != p["Map_Blaze"]
    )
    both = sum(1 for f in features if (p := f.get("properties") or {}).get("Blaze") and p.get("Map_Blaze"))
    known = {v: n for v, n in values.items() if v in client_colors}
    novel = {v: n for v, n in values.items() if v and v not in client_colors}
    return {
        "unblazed_or_unrecorded": values.get(None, 0) + values.get("", 0),
        "client_palette_hits": known,
        "novel_to_client": dict(sorted(novel.items(), key=lambda kv: -kv[1])),
        "blaze_vs_map_blaze_disagreements": (disagree, both),
    }


def to_meters(line) -> LineString:
    xs, ys = WGS84_TO_UTM18.transform(*zip(*line.coords))
    return LineString(zip(xs, ys))


def offset_stats(subject_lines: list, other_lines: list, stride_m: float = SAMPLE_STRIDE_M) -> dict:
    """Sample points every `stride_m` along `subject_lines` and measure each
    point's distance to the union of `other_lines`, in meters. This is both
    the AT-vs-OPRHP's-own-AT divergence measurement and the how-close-is-the-
    nearest-other-trail exposure the wrong-way question needs."""
    others = unary_union([to_meters(line) for line in other_lines])
    distances = []
    for line in subject_lines:
        metered = to_meters(line)
        d = 0.0
        while d <= metered.length:
            distances.append(metered.interpolate(d).distance(others))
            d += stride_m
    if not distances:
        return {"samples": 0}
    distances.sort()
    return {
        "samples": len(distances),
        "median_m": round(statistics.median(distances), 1),
        "p95_m": round(distances[int(0.95 * (len(distances) - 1))], 1),
        "max_m": round(distances[-1], 1),
        "share_within_150m": round(sum(1 for x in distances if x <= 150) / len(distances), 3),
    }


def flatten_lines(features: list[dict]) -> list:
    lines = []
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        geom = shape(geometry)
        lines.extend(geom.geoms if isinstance(geom, MultiLineString) else [geom])
    return lines


def clip_lines(lines: list, boundary) -> list:
    """Line parts inside `boundary`. The first run of this spike skipped this
    and its divergence tails read in kilometers — not divergence at all, but
    the ATC centerline and the Long Path continuing past the ground OPRHP
    maps. A subject clipped to where the compared source claims coverage is
    the only honest comparison; the unclipped version measures the boundary."""
    clipped = []
    for line in lines:
        inter = line.intersection(boundary)
        if inter.is_empty:
            continue
        if isinstance(inter, LineString):
            clipped.append(inter)
        elif isinstance(inter, MultiLineString):
            clipped.extend(inter.geoms)
        else:  # GeometryCollection from touching edges - keep the line parts
            clipped.extend(g for g in getattr(inter, "geoms", []) if isinstance(g, LineString))
    return clipped


def parks_boundary():
    """The union of the two parks' polygons, from the layer #769 registered —
    the honest 'where OPRHP maps trails' boundary for the clips above."""
    fc = json.loads(OPRHP_PARKS.read_text())
    polys = [
        shape(f["geometry"])
        for f in fc["features"]
        if (f.get("properties") or {}).get("Label") in AREA_FACILITIES and f.get("geometry")
    ]
    return unary_union(polys)


# --- Fetch-and-cache for the two overlay lines ------------------------------


def fetch_bbox_cached(url: str, cache_name: str, bbox: tuple) -> list[dict]:
    """One envelope query against an ArcGIS layer, cached under SPIKE_DIR so
    a re-measurement costs upstream nothing (spike_poi_duplicates' posture)."""
    cache = SPIKE_DIR / cache_name
    if cache.exists():
        return json.loads(cache.read_text())["features"]
    west, south, east, north = bbox
    response = requests.get(
        url.rstrip("/") + "/query",
        params={
            "where": "1=1",
            "geometry": json.dumps({"xmin": west, "ymin": south, "xmax": east, "ymax": north}),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "outSR": 4326,
            "f": "geojson",
        },
        timeout=60,
    )
    response.raise_for_status()
    fc = response.json()
    SPIKE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(fc))
    return fc["features"]


def atc_centerline_url() -> str:
    registry = json.loads((ROOT / "sources.json").read_text())
    return next(s["url"] for s in registry["sources"] if s["key"] == "centerline")


# --- The run ----------------------------------------------------------------


def main() -> None:
    fc = json.loads(OPRHP_TRAILS.read_text())
    area = [f for f in fc["features"] if ((f.get("properties") or {}).get("Facility") or "").strip() in AREA_FACILITIES]
    print(f"OPRHP segments in {' + '.join(AREA_FACILITIES)}: {len(area)}")

    hiking, dropped = keep_hiking(area)
    print(f"after hiking-only + Status filter: {len(hiking)}  (dropped: {dict(dropped)})")

    miles = sum((f.get("properties") or {}).get("Miles") or 0 for f in hiking)
    print(f"trail miles kept: {miles:.1f}")

    groups = named_groups(hiking)
    chains = chain_report(groups)
    print(f"\nnamed trails: {chains['named_trails']}  |  merge to a single chain: {chains['single_chain']}")
    print(f"unnamed segments (woods roads etc.): {chains['unnamed_segments']}")
    print("multi-part trails (name -> parts):")
    for name, n in list(chains["multi_part"].items())[:12]:
        print(f"   {name}: {n}")

    print(f"\njunctions where different named trails meet: {junction_count(hiking)}")

    client_palette = {"White", "Blue", "Yellow", "Orange", "Red", "Green", "Purple"}
    blazes = blaze_report(hiking, client_palette)
    print(f"\nblaze: unrecorded {blazes['unblazed_or_unrecorded']} of {len(hiking)}")
    print(f"   in client palette: {blazes['client_palette_hits']}")
    print(f"   novel to client:   {blazes['novel_to_client']}")
    d, both = blazes["blaze_vs_map_blaze_disagreements"]
    print(f"   Blaze vs Map_Blaze disagree: {d} of {both} rows carrying both")

    # The AT through Harriman: ATC's line (the shipped source of record)
    # against OPRHP's own copy, and against everyone else's trails. Both
    # subjects are clipped to the parks first — see clip_lines' docstring.
    boundary = parks_boundary()
    at_features = fetch_bbox_cached(atc_centerline_url(), "at_centerline_harriman.geojson", AREA_BBOX)
    at_in_parks = clip_lines(flatten_lines(at_features), boundary)
    at_miles = sum(to_meters(line).length for line in at_in_parks) / METERS_PER_MILE
    print(f"\nATC centerline inside the two parks: {len(at_in_parks)} parts, {at_miles:.1f} mi")

    oprhp_at = [f for f in hiking if "appalachian" in ((f.get("properties") or {}).get("Name") or "").lower()]
    others = [f for f in hiking if f not in oprhp_at]
    print(f"OPRHP rows naming the Appalachian Trail: {len(oprhp_at)}")
    if oprhp_at:
        divergence = offset_stats(at_in_parks, flatten_lines(oprhp_at))
        print(f"   ATC line vs OPRHP's AT copy (in-park): {divergence}")

    exposure = offset_stats(at_in_parks, flatten_lines(others))
    print(f"AT's distance to the NEAREST OTHER trail, in-park (wrong-way exposure): {exposure}")

    lp_features = fetch_bbox_cached(LONG_PATH_URL, "long_path_harriman.geojson", AREA_BBOX)
    lp_in_parks = clip_lines(flatten_lines(lp_features), boundary)
    lp_miles = sum(to_meters(line).length for line in lp_in_parks) / METERS_PER_MILE
    print(f"\nNYNJTC Long Path inside the two parks: {len(lp_in_parks)} parts, {lp_miles:.1f} mi")
    oprhp_lp = [f for f in hiking if "long path" in ((f.get("properties") or {}).get("Name") or "").lower()]
    lp_blazes = Counter((f.get("properties") or {}).get("Blaze") for f in oprhp_lp)
    print(f"OPRHP rows naming the Long Path: {len(oprhp_lp)}  (their Blaze: {dict(lp_blazes)})")
    if lp_in_parks and oprhp_lp:
        lp_div = offset_stats(lp_in_parks, flatten_lines(oprhp_lp))
        print(f"   NYNJTC Long Path vs OPRHP's copy (in-park): {lp_div}")

    # A trails.geojson-shaped artifact for the window, for #772's eyes and
    # #552's scales. Kept in gitignored spike space; nothing publishes it.
    out = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "id": f"oprhp:{(f.get('properties') or {}).get('GlobalID')}",
                    "source": "oprhp_trails",
                    "name": (f.get("properties") or {}).get("Name"),
                    "blaze_color": (f.get("properties") or {}).get("Blaze") or "Unknown",
                    "facility": (f.get("properties") or {}).get("Facility"),
                    "miles": (f.get("properties") or {}).get("Miles"),
                    "status": (f.get("properties") or {}).get("Status"),
                },
            }
            for f in hiking
        ],
    }
    SPIKE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SPIKE_DIR / "harriman_trails.geojson"
    out_path.write_text(json.dumps(out))
    raw = out_path.stat().st_size
    gz = len(gzip.compress(out_path.read_bytes()))
    print(f"\nartifact: {out_path}  {raw / 1e6:.1f} MB raw, {gz / 1e6:.2f} MB gzipped")
    if SHIPPED_TRAILS.exists():
        print(f"shipped AT trails.geojson for comparison: {SHIPPED_TRAILS.stat().st_size / 1e6:.1f} MB raw")
    else:
        print(
            "(shipped trails.geojson not built in this checkout - compare against 12.3 MB raw / 4.1 MB gz, measured 2026-08-15 in client/src/lib/config.ts)"
        )


if __name__ == "__main__":
    main()
