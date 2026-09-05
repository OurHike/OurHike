"""How far off the trail every published waypoint actually sits (#1101).

#1101 names the gap and refuses to guess at it:

    "PoiDetail carries no per-waypoint offset, and nothing in the pipeline
    publishes one... Until that exists, nobody can say whether this is a
    useful line or a misleading one, and the answer may be 'useful for some
    types and not others'."

THE NUMBER UNDER SUSPICION is the mock-up's. #941's design pass drew the
card's second line as `0.3 mi ahead, 20 ft off trail`, and #1101's argument
for measuring before rendering is that `wrongWay.ts` already records 72% of
shelters sitting past `OFF_TRAIL_THRESHOLD_FT` (90 ft) - so 20 ft may be a
designer's round number rather than a typical value, and a card printing it
as typical would teach hikers the wrong scale.

THIS IS A SPIKE, and the code is throwaway. What should survive is the SHAPE
of the answer - the distribution per POI type, and the gap between the two
distances below - not this file. The pure helpers are kept honest by
tests/test_spike_poi_trail_offset.py; the measurement half needs the live
artifacts.

ONLY WAYPOINTS THAT ARE ON THE A.T. ARE MEASURED, and finding out why is
half of what this spike learned. 4,311 of the 8,469 published waypoints
(50.9%) carry `mile: null` - 4,192 crossings and 119 water - and they sit a
median of 54 miles from the centerline, out to 222. That is not a defect:
`export_poi.mark_off_trail_records` (#1016) WITHHOLDS the A.T. mile from a
waypoint on somebody else's trail on purpose, because `attach_miles` "projects
onto the nearest point of the A.T. and always succeeds - there is no distance
at which it declines", and a Harriman spring carrying a perfectly formed mile
would become a candidate stop in an A.T. itinerary.

So `mile is not None` is the population a card's "N ft off trail" line would
describe, and it is the only population measured below. Measuring the rest
would answer a question nobody asked - how far a New Jersey stream crossing is
from a trail it was never on - and would have buried the on-trail distribution
under it. The split is reported so the reader can see it was made.

TWO DISTANCES, NOT ONE, AND THE GAP BETWEEN THEM IS THE POINT

#1101's step 2 says the meaning has to be decided in the open: "A straight-line
offset from the centerline is not the walk: a shelter 200 ft off as the crow
flies can be a 0.2 mi switchback down." There is a second, larger discrepancy
that the issue does not name, and this spike exists partly to surface it:
`trails.geojson` carries 1,196 `side_trails` features beside its 461
`centerline` ones, so a waypoint far from the A.T. may be a few steps from a
blue-blazed spur that leads to it. Measuring only to the centerline would
report a bushwhack where there is a path.

So both are reported per type:

    centerline   nearest point on `source == 'centerline'` - the A.T. itself.
                 This is what "off trail" means in wrongWay.ts and
                 trailPosition.ts, which measure a HIKER's distance from the
                 tread, and therefore what a card's line would be read against.
    any trail    nearest point on any feature in trails.geojson, side trails
                 included. Still not the walk - a spur's LENGTH is the walk,
                 and that is build_water_distance.py's quantity - but it
                 bounds how much of the centerline offset is explained by a
                 path somebody could actually follow.

NEITHER IS THE WALKED DISTANCE, and nothing here should be published as
though it were. Both are perpendicular straight-line distances. The water
pipeline already chose the walked spur where a source has one
(build_water_distance.py); #1101 step 2 is the decision to make the same call
in the open for the general case, and this measurement is its input, not its
answer.

PROJECTION. EPSG:5070 (NAD83 Conus Albers), the same equal-area metric CRS
lib/corridor.py buffers in and export_network_elevation.py measures length in.
Distances come out in metres and are reported in feet, because
OFF_TRAIL_THRESHOLD_FT is in feet and comparing against it is half the point.

NOTHING PUBLISHES and nothing is committed. The fetch is cached under
data/spike/poi_trail_offset/, gitignored like everything under data/ -
CONTRIBUTING.md's "Data does not go in commits".

Run:  python spike_poi_trail_offset.py            # reads the cache
      python spike_poi_trail_offset.py --fetch    # populate it first
"""

from __future__ import annotations

import argparse
import json
import statistics
import urllib.request
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "data" / "spike" / "poi_trail_offset"
BASE_URL = "https://data.ourhike.org"

GEOGRAPHIC_CRS = "EPSG:4326"
PROJECTED_CRS = "EPSG:5070"

METERS_PER_FOOT = 0.3048

#: client/src/lib/wrongWay.ts. Read rather than re-derived: one threshold is
#: the whole evidence that it is a measurement and not a knob.
OFF_TRAIL_THRESHOLD_FT = 90

POI_TYPES = ("shelter", "water", "campsite", "resupply", "crossing", "viewpoint", "parking", "privy", "trailhead")

TRAILS_NAME = "trails.geojson"


def artifact_names() -> list[str]:
    return [TRAILS_NAME, *(f"poi_{poi_type}.geojson" for poi_type in POI_TYPES)]


def fetch(names: list[str] | None = None) -> None:
    """Populate the cache. Separate from the measurement so a re-run costs
    nothing and so the network is never touched by a test."""
    CACHE.mkdir(parents=True, exist_ok=True)
    for name in names or artifact_names():
        target = CACHE / name
        if target.exists():
            print(f"  cached  {name}")
            continue
        print(f"  fetch   {name}")
        with urllib.request.urlopen(f"{BASE_URL}/{name}", timeout=180) as response:
            target.write_bytes(response.read())


def _to_projected():
    """always_xy because every coordinate here is (lon, lat) and pyproj's
    authority-order default would swap them - the note build_trail_graph.py
    and export_network_elevation.py both carry."""
    transformer = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True)
    return lambda x, y: transformer.transform(x, y)


def load_trails(path: Path) -> tuple[list, list]:
    """(centerline geometries, every trail geometry), projected.

    Split on `source`, which trails.geojson carries on every feature:
    `centerline` is the A.T., `side_trails` is everything blue-blazed beside
    it. Reported separately because a waypoint's distance to the A.T. and its
    distance to the nearest path a hiker could follow are different questions
    and the card would be answering only one of them.
    """
    project = _to_projected()
    collection = json.loads(path.read_text(encoding="utf-8"))
    centerline, every = [], []
    for feature in collection["features"]:
        geometry = shapely_transform(project, shape(feature["geometry"]))
        every.append(geometry)
        if feature["properties"].get("source") == "centerline":
            centerline.append(geometry)
    return centerline, every


def offsets_feet(points: list, trees: STRtree, geometries: list) -> list[float]:
    """Each point's distance to the nearest trail geometry, in feet.

    STRtree.nearest returns an INDEX into the geometries it was built from, so
    the distance still has to be taken against that geometry - the tree
    answers "which one", not "how far".
    """
    out = []
    for point in points:
        nearest = geometries[trees.nearest(point)]
        out.append(point.distance(nearest) / METERS_PER_FOOT)
    return out


def summarise(values: list[float]) -> dict:
    """The distribution, not the mean. A mean would hide exactly the tail this
    measurement exists to look at - one shelter a mile off drags it, and the
    question is what a TYPICAL waypoint looks like beside the mock-up's 20 ft.
    """
    if not values:
        return {"n": 0}
    ordered = sorted(values)

    def pct(p: float) -> float:
        return ordered[min(int(p * len(ordered)), len(ordered) - 1)]

    return {
        "n": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p75": pct(0.75),
        "p90": pct(0.90),
        "p95": pct(0.95),
        "max": ordered[-1],
        "past_threshold_pct": 100.0 * sum(1 for v in ordered if v > OFF_TRAIL_THRESHOLD_FT) / len(ordered),
        "under_20ft_pct": 100.0 * sum(1 for v in ordered if v <= 20.0) / len(ordered),
    }


def _row(label: str, s: dict) -> str:
    if not s.get("n"):
        return f"  {label:11} (no features published)"
    return (
        f"  {label:11} {s['n']:5d}  {s['min']:8.0f} {s['median']:8.0f} {s['p75']:8.0f} "
        f"{s['p90']:9.0f} {s['p95']:9.0f} {s['max']:10.0f}  {s['past_threshold_pct']:6.1f}%  {s['under_20ft_pct']:6.1f}%"
    )


#: Beyond this, a waypoint is worth naming individually rather than counting.
#: Not a threshold anything enforces - a reporting cutoff, chosen so the tail
#: fits on a screen.
FAR_CUTOFF_FT = 5280.0


def far_records(features: list, project, tree: STRtree, geometries: list, poi_type: str) -> list[tuple[float, str, dict]]:
    """On-A.T. waypoints sitting more than a mile from the A.T.

    Reported because the tail is where the card's line would matter most and
    where it is easiest to mistake a correct number for a broken one. Most of
    these are RIGHT: a `resupply` is a town and towns are miles off the trail
    by nature, and Dockery Lake, Undermountain and West Mountain are real long
    side trails. Listing them is what lets a reader check that rather than
    infer it.
    """
    out = []
    for feature in features:
        if feature["properties"].get("mile") is None:
            continue
        point = shapely_transform(project, shape(feature["geometry"]))
        feet = point.distance(geometries[tree.nearest(point)]) / METERS_PER_FOOT
        if feet > FAR_CUTOFF_FT:
            out.append((feet, poi_type, feature["properties"]))
    return out


def measure() -> dict:
    centerline, every = load_trails(CACHE / TRAILS_NAME)
    centerline_tree, every_tree = STRtree(centerline), STRtree(every)
    project = _to_projected()

    results: dict[str, dict] = {}
    far: list[tuple[float, str, dict]] = []
    for poi_type in POI_TYPES:
        path = CACHE / f"poi_{poi_type}.geojson"
        if not path.exists():
            continue
        collection = json.loads(path.read_text(encoding="utf-8"))
        features = collection["features"]
        # The #1016 split, above. A waypoint with no A.T. mile is one the
        # pipeline has already established is not on the A.T., so its distance
        # to the A.T. is not the number a card would print.
        on_trail = [f for f in features if f["properties"].get("mile") is not None]
        points = [shapely_transform(project, shape(f["geometry"])) for f in on_trail]
        results[poi_type] = {
            "published": len(features),
            "off_at": len(features) - len(on_trail),
            "centerline": summarise(offsets_feet(points, centerline_tree, centerline)),
            "any_trail": summarise(offsets_feet(points, every_tree, every)),
        }
        far.extend(far_records(features, project, centerline_tree, centerline, poi_type))
    results["_far"] = sorted(far, key=lambda row: -row[0])
    return results


def report(results: dict) -> None:
    far = results.pop("_far", [])
    header = f"  {'type':11} {'n':>5}  {'min':>8} {'median':>8} {'p75':>8} {'p90':>9} {'p95':>9} {'max':>10}  {'>90ft':>7}  {'<=20ft':>7}"
    for which, title in (
        ("centerline", "TO THE A.T. CENTERLINE"),
        ("any_trail", "TO THE NEAREST TRAIL OF ANY KIND (side trails included)"),
    ):
        print(f"\n{title}   -   feet")
        print(header)
        for poi_type, both in results.items():
            print(_row(poi_type, both[which]))

    print("\nWHAT #1016 ALREADY HELD BACK (waypoints with no A.T. mile, not measured above)")
    print(f"  {'type':11} {'published':>10} {'no mile':>9} {'measured':>9}")
    for poi_type, both in results.items():
        print(f"  {poi_type:11} {both['published']:10d} {both['off_at']:9d} {both['centerline'].get('n', 0):9d}")

    print("\nWHAT MOVES WHEN SIDE TRAILS COUNT (median, feet)")
    print(f"  {'type':11} {'centerline':>11} {'any trail':>11} {'closed by':>11}")
    for poi_type, both in results.items():
        c, a = both["centerline"], both["any_trail"]
        if not c.get("n"):
            continue
        print(f"  {poi_type:11} {c['median']:11.0f} {a['median']:11.0f} {c['median'] - a['median']:11.0f}")

    print(f"\nCARRY AN A.T. MILE YET SIT OVER A MILE FROM IT ({len(far)} waypoints)")
    print("  Most are correct - a resupply is a town. Listed so that can be checked.")
    for feet, poi_type, props in far[:12]:
        print(
            f"   {feet:8.0f} ft ({feet / 5280:5.2f} mi)  mile={str(props.get('mile')):>9}  {poi_type:9} {str(props.get('name'))[:40]!r}"
        )
    if len(far) > 12:
        print(f"   ... and {len(far) - 12} more")


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fetch", action="store_true", help="download the artifacts into the cache first")
    args = parser.parse_args(argv)
    if args.fetch:
        fetch()
    results = measure()
    report(results)
    return results


if __name__ == "__main__":
    main()
