"""Where the pin/corridor seam goes (features/POI_VISIBILITY.md, #593).

Answers one question, and only one: **at what zoom does a phone screen stop
being oversubscribed with waypoints?** That zoom is `POI_PIN_MIN_ZOOM` — below
it the map is the corridor view (features/CORRIDOR_VIEW.md), above it every
waypoint draws as a pin or a dot.

WHY THIS EXISTS RATHER THAN AN ARGUMENT

POI_VISIBILITY.md's arithmetic could only bracket the answer to z12-z13, and
its predecessor got three issues' worth of design out of a figure measured at
one zoom and generalised to all of them. #531 asked for four zoom tiers "not
validated" and never got them validated. One number, produced.

WHAT IT DOES DIFFERENTLY FROM features/POI_SITES.md's TABLE

Same method - symbols considered in `symbol-sort-key` order, a box skipped
when it overlaps one already placed - with two changes that are the whole
point:

  - It runs against the SITE-FOLDED point set. Folding is what changes the
    answer: lib/poi_sites.py collapses co-located waypoints onto one anchor,
    and a member riding a drawn anchor's pin is reachable. Simulating the
    unfolded set measures a map this design is not building.
  - It extends below z12, where nothing had been simulated and where the
    seam actually is.

It also reports the viewport LOAD, which is the criterion the drawn-share
table cannot express: a category can be 80% drawn because it is sparse, on a
screen that is still hopelessly crowded overall.

NO NETWORK - it reads data/raw/<key>.geojson, which fetch_all.py writes, the
same way spike_corridor.py and spike_photo_scope.py do. Run fetch_all.py
first.

WHAT IS NOT IN THE MEASUREMENT, AND SAYING SO IS THE POINT

  - **Water.** It comes from opentrail.org, whose API needs more than a bare
    GET, so fetch_all.py does not write it here. features/POI_SITES.md's own
    measured table carries the same gap for the same reason. Water is first
    in POI_PRIORITY, so its absence makes the survivors below it look very
    slightly better than they are: 174 points against 2,532.
  - **Corridor clipping.** These are the raw layers, so 1,223 viewpoints
    where the corridor holds 1,194. That cuts the other way - very slightly
    more crowding than the app ships.
  - **resupply and crossing**, which come from opentrail too.

Neither gap is near large enough to move a seam that sits between a median
load of 18 and a median load of 9.

THIS IS A SPIKE. What survives is the number and this file as the way to
re-derive it against fresher data; the arithmetic is not shipped anywhere.
"""

import argparse
import bisect
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

from lib.poi_sites import group_sites

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"

# data/raw/<key>.geojson -> the poi_type export_poi.py gives that layer. Its
# module docstring calls these "~1:1 with poi_type", which is what makes a
# layer-keyed table honest here rather than a second taxonomy.
LAYER_TYPES = {
    "campsites": "campsite",
    "parking": "parking",
    "privies": "privy",
    "shelters": "shelter",
    "viewpoints": "viewpoint",
}

# client/src/map/poiLayers.ts POI_PRIORITY, in full. The types this fetch has
# no source for are kept in the list rather than trimmed out of it, so the
# ordering here can be diffed against that file without a mental step.
POI_PRIORITY = ["water", "shelter", "campsite", "resupply", "parking", "privy", "crossing", "viewpoint"]

# POI_PIN_SIZE (38) + icon-padding (2) on each side. Two pins collide when
# their centres are closer than this in BOTH axes - the boxes are axis-aligned
# and MapLibre tests them as boxes, not as circles.
PIN_BOX_PX = 42.0

# WIREFRAMES.md's phone map area, which is what the seam is a judgement about.
VIEWPORT_W_PX = 390.0
VIEWPORT_H_PX = 700.0

# MapLibre uses 512 px tiles, not 256. Getting this wrong is a whole zoom
# level of error and it looks plausible either way, which is why it is a named
# constant with this comment on it rather than a 512 in the middle of a line.
TILE_PX = 512.0


@dataclass(frozen=True)
class ZoomResult:
    zoom: int
    drawn_share: dict[str, float]
    """poi_type -> share of that type reachable on the map."""
    loads: list[int]
    """Waypoints inside a phone viewport centred on each waypoint in turn."""

    @property
    def median_load(self) -> float:
        return statistics.median(self.loads)

    @property
    def p90_load(self) -> float:
        return statistics.quantiles(self.loads, n=10)[8]

    @property
    def p99_load(self) -> float:
        return statistics.quantiles(self.loads, n=100)[98]


def pin_room() -> int:
    """How many pins fit down a straight column of viewport.

    The trail wanders sideways, so a real screen holds somewhat more than this
    - it is the conservative reading, and the seam should be chosen against
    the conservative one.
    """
    return int(VIEWPORT_H_PX / PIN_BOX_PX)


def to_pixels(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Web Mercator pixel coordinates at `zoom`, on MapLibre's 512 px grid."""
    world = TILE_PX * (2.0**zoom)
    lat_rad = math.radians(lat)
    x = (lon + 180.0) / 360.0 * world
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * world
    return x, y


def sort_key(record: dict) -> int:
    """`symbol-sort-key`, as POI_SORT_KEY_EXPRESSION computes it: the index in
    POI_PRIORITY, and unknown types last."""
    try:
        return POI_PRIORITY.index(record["poi_type"])
    except ValueError:
        return len(POI_PRIORITY)


def place(records: list[dict], zoom: int) -> set[str]:
    """The ids MapLibre would draw: greedy placement in sort-key order, a box
    skipped when it overlaps one already placed.

    Ties inside a priority are broken by id, so a re-run over unchanged input
    returns the same set - a set-iteration order here would make the whole
    table wobble between runs and be very hard to notice.

    Bucketed into a grid of one box per cell so this is not quadratic: 2,500
    points at eight zooms with an all-pairs test is minutes, and a spike
    nobody wants to run is a spike nobody re-runs.
    """
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    drawn: set[str] = set()
    for record in sorted(records, key=lambda r: (sort_key(r), r["id"])):
        x, y = to_pixels(record["lat"], record["lon"], zoom)
        cell_x, cell_y = int(x // PIN_BOX_PX), int(y // PIN_BOX_PX)
        collides = any(
            abs(px - x) < PIN_BOX_PX and abs(py - y) < PIN_BOX_PX
            for gx in (cell_x - 1, cell_x, cell_x + 1)
            for gy in (cell_y - 1, cell_y, cell_y + 1)
            for px, py in grid.get((gx, gy), ())
        )
        if not collides:
            grid.setdefault((cell_x, cell_y), []).append((x, y))
            drawn.add(record["id"])
    return drawn


def viewport_loads(records: list[dict], zoom: int) -> list[int]:
    """How many waypoints a phone viewport holds, centred on each waypoint.

    Centred on a waypoint rather than on a grid over the corridor, because
    that is the screen a hiker actually has: nobody looks at an empty stretch
    of Pennsylvania on purpose. A grid would average the trail's crowding
    together with the space between it and report a number no hiker ever sees.
    """
    points = sorted(to_pixels(r["lat"], r["lon"], zoom) for r in records)
    xs = [x for x, _ in points]
    half_w, half_h = VIEWPORT_W_PX / 2, VIEWPORT_H_PX / 2
    loads = []
    for x, y in points:
        lo = bisect.bisect_left(xs, x - half_w)
        hi = bisect.bisect_right(xs, x + half_w)
        loads.append(sum(1 for i in range(lo, hi) if abs(points[i][1] - y) <= half_h))
    return loads


def reachable(records: list[dict], zoom: int) -> set[str]:
    """Every waypoint a hiker can get to at `zoom`, site-folding included.

    A member whose anchor is drawn is reachable - that is the entire claim of
    features/POI_SITES.md, that a privy stops competing for a pin and starts
    riding one. A member whose anchor lost its own collision is not.
    """
    sites = group_sites(records)
    member_ids = {m["id"] for s in sites for m in s.members}
    anchors_and_singles = [r for r in records if r["id"] not in member_ids]

    drawn = place(anchors_and_singles, zoom)
    out = set(drawn)
    for site in sites:
        if site.anchor["id"] in drawn:
            out.update(m["id"] for m in site.members)
    return out


def load_records(raw_dir: Path = RAW_DIR) -> list[dict]:
    """The five ATC facility layers as {id, poi_type, name, lat, lon}.

    Deliberately minimal: lib/poi_sites.py needs exactly these five keys, and
    a record carrying more would invite this spike to start answering a
    different question than the one in its docstring.
    """
    records = []
    for key, poi_type in sorted(LAYER_TYPES.items()):
        path = raw_dir / f"{key}.geojson"
        if not path.exists():
            raise SystemExit(f"{path} is missing - run fetch_all.py first")
        collection = json.loads(path.read_text())
        for feature in collection.get("features", []):
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates")
            if not coords or len(coords) < 2 or coords[0] is None or coords[1] is None:
                continue
            properties = feature.get("properties") or {}
            records.append(
                {
                    "id": f"atc_{key}:{properties.get('GlobalID')}",
                    "poi_type": poi_type,
                    "name": properties.get("Name"),
                    "lat": coords[1],
                    "lon": coords[0],
                }
            )
    return records


def measure(records: list[dict], zooms: range) -> list[ZoomResult]:
    types = sorted({r["poi_type"] for r in records})
    totals = {t: sum(1 for r in records if r["poi_type"] == t) for t in types}
    sites = group_sites(records)
    member_ids = {m["id"] for s in sites for m in s.members}
    pin_bearing = [r for r in records if r["id"] not in member_ids]

    results = []
    for zoom in zooms:
        reach = reachable(records, zoom)
        results.append(
            ZoomResult(
                zoom=zoom,
                drawn_share={t: sum(1 for r in records if r["poi_type"] == t and r["id"] in reach) / totals[t] for t in types},
                loads=viewport_loads(pin_bearing, zoom),
            )
        )
    return results


def seam(results: list[ZoomResult]) -> int | None:
    """The lowest zoom whose MEDIAN viewport is not oversubscribed.

    The median rather than the p90, and the reason is the dot rank: above the
    seam an oversubscribed screen costs dots, not deletions, so the criterion
    is "is this a better screen than the corridor view" and not "is this
    screen guaranteed to fit". Choosing on the p90 would push the seam a level
    deeper to protect against a case that is no longer a failure.
    """
    room = pin_room()
    for result in results:
        if result.median_load <= room:
            return result.zoom
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--min-zoom", type=int, default=10)
    parser.add_argument("--max-zoom", type=int, default=17)
    args = parser.parse_args()

    records = load_records(args.raw_dir)
    sites = group_sites(records)
    folded = sum(len(s.members) for s in sites)
    print(f"{len(records)} waypoints -> {len(sites)} sites folding {folded} members")
    print(f"a phone viewport holds about {pin_room()} pins down a straight column\n")

    results = measure(records, range(args.min_zoom, args.max_zoom + 1))
    types = sorted(results[0].drawn_share)

    header = "zoom | " + " | ".join(f"{t:>9}" for t in types) + " | median | p90 | p99 | fits?"
    print("SHARE REACHABLE (site-folded), AND WHAT A 390x700 VIEWPORT HOLDS\n")
    print(header)
    print("-" * len(header))
    room = pin_room()
    for r in results:
        row = f"  {r.zoom:>2} | " + " | ".join(f"{r.drawn_share[t]:>8.0%}" for t in types)
        row += f" | {r.median_load:>6.0f} | {r.p90_load:>3.0f} | {r.p99_load:>3.0f} | "
        row += "yes" if r.median_load <= room else "NO"
        print(row)

    answer = seam(results)
    print(f"\nPOI_PIN_MIN_ZOOM = {answer}" if answer else "\nno zoom in range fits - widen --max-zoom")


if __name__ == "__main__":
    main()
