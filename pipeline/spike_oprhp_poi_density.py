"""How many pins a park actually puts on one z12 screen (#936).

features/NEARBY_TRAILS.md §10 names the gap and declines to guess at it:

    "Amenities-chosen-only was decided partly on an unmeasured fear:
    Harriman-scale POI density. It is still unmeasured - OPRHP's facilities
    layer holds 8,823 points statewide and nobody has counted the two parks'
    safety-relevant subset at z12."

A real display rule rests on that fear. #783 shipped the split frame `1g`
states to hikers - water, closures and warnings draw for every trail on
screen; shelters, privies and viewpoints stay on the trail you chose - and
the amenity half was chosen partly because nobody knew how many pins a park
would produce. If the fear was wrong the rule is more restrictive than it
needs to be; if it was right the safety half may itself need POI_VISIBILITY.md's
dot rank. Either way it is a rule standing on an estimate.

THIS IS A SPIKE, and the code is throwaway. What should survive is the SHAPE
of the answer - how many safety-relevant points the two parks hold, and how
many of them land in one phone screen at the densest place - not this file.
The pure helpers are kept honest by tests/test_spike_oprhp_poi_density.py;
the measurement half needs the live layer.

NOTHING PUBLISHES. The OPRHP licence answers (#768/#769) still gate that, and
this is the "may be fetched for review" case #936 names. The fetch is cached
under data/spike/oprhp_density/, which is gitignored like everything under
data/ - CONTRIBUTING.md's "Data does not go in commits".

Run:  python spike_oprhp_poi_density.py
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

FACILITIES_URL = "https://services.arcgis.com/1xFZPtKn1wKC6POA/arcgis/rest/services/NY_State_Park_Facilities/FeatureServer/0"

# The two parks #936 names. `Facility` is OPRHP's own park-name column - the
# schema marks it "(Legacy Field)", which is worth knowing and does not matter
# here: it is populated on every row the two parks hold, and the layer offers
# no other park identifier.
PARKS = ("Harriman State Park", "Bear Mountain State Park")

CACHE = Path("data/spike/oprhp_density")

# WHAT COUNTS AS SAFETY-RELEVANT, AND WHY IT IS TWO ANSWERS RATHER THAN ONE.
#
# NEARBY_TRAILS.md's decisions table names the safety kinds exactly: "water,
# closures, serious warnings". Closures and warnings are not facilities - they
# arrive as a mile range and as a moderated report - so the only safety kind
# this layer can supply is WATER.
#
# #936's own text says "water, privies - the categories §1's always-draw rule
# admits", which is a wider reading: a privy is an amenity in POI_TYPES and is
# not in that table's triple. Rather than pick one and bury the choice, this
# counts both and prints both, because the two answers support different
# decisions and the difference between them is itself a finding.
WATER = frozenset({"Drinking Fountain", "Water Spigot"})

# Read as facilities rather than as our own `privy` type: a public restroom in
# a state park is a building, and a pit toilet is the backcountry thing our
# `privy` pin means. Both are counted because #936's question is about how many
# PINS a park puts on a screen, and OurHike would draw either.
TOILETS = frozenset({"Pit Toilet", "Portable Toilet", "Public Restroom"})

# The amenity half of #783's split, restricted to what OurHike actually has a
# pin for (POI_TYPES): shelter, campsite, parking, viewpoint, resupply, privy.
# `Trailhead` is included because it is the one facility a hiker navigates to
# that has no POI_TYPES home and would obviously be drawn if this layer shipped
# - counted separately below so it can be removed from the answer if not.
AMENITIES = frozenset(
    {
        "Lean-to",  # shelter
        "Campground",  # campsite
        "Group Camp",  # campsite
        "Parking Area",  # parking
        "Accessible Parking Area",  # parking
        "Scenic View",  # viewpoint
        "Wildlife Viewpoint",  # viewpoint
        "Waterfall",  # viewpoint
        "Store",  # resupply
        "Concession",  # resupply
        "Trailhead",
    }
)

# A 390 x 700 phone map, which is POI_VISIBILITY.md's own viewport and the one
# its density table is computed for.
VIEWPORT_W_PX = 390
VIEWPORT_H_PX = 700
ZOOM = 12

# MapLibre's zoom, not the 256-tile slippy convention, and the difference is a
# factor of two in linear ground. POI_VISIBILITY.md's table is the calibration:
# it puts z12 at "14.6 m/px at 40degN", and 156543.03392 * cos(40) / 2**12 is
# 29.3 - twice that - while / 2**13 is 14.64. So the exponent is z + 1, which is
# what a 512 px tile means. Matching that table is the point: an answer computed
# in the other convention would be about a screen twice the size and would
# silently disagree with the one document this question is asked against.
EQUATOR_M_PER_PX_Z0 = 156543.03392804097


def metres_per_pixel(latitude: float, zoom: int = ZOOM) -> float:
    """Ground metres per CSS pixel at a latitude, in MapLibre's zoom."""
    return EQUATOR_M_PER_PX_Z0 * math.cos(math.radians(latitude)) / 2 ** (zoom + 1)


def viewport_degrees(latitude: float, zoom: int = ZOOM) -> tuple[float, float]:
    """The phone map's width and height at a latitude, in degrees lon/lat."""
    m_per_px = metres_per_pixel(latitude, zoom)
    width_m = VIEWPORT_W_PX * m_per_px
    height_m = VIEWPORT_H_PX * m_per_px
    # One degree of latitude is ~111,320 m; one of longitude shrinks by cos.
    lat_deg = height_m / 111_320.0
    lon_deg = width_m / (111_320.0 * math.cos(math.radians(latitude)))
    return lon_deg, lat_deg


@dataclass(frozen=True)
class Point:
    lon: float
    lat: float
    sub_asset: str
    park: str


def densest_window(points: list[Point], lon_deg: float, lat_deg: float) -> tuple[int, tuple[float, float] | None]:
    """The most points any one viewport-sized window can hold, and where.

    Anchored on the points themselves rather than swept on a grid: a window
    whose south-west corner is not on a point can always be slid until it is
    without losing anything, so the maximum over point-anchored windows IS the
    maximum. O(n^2) over a few hundred points, which is nothing, and exact -
    a grid sweep would depend on the grid's phase and could miss a cluster
    straddling two cells.
    """
    best = 0
    where: tuple[float, float] | None = None
    for anchor in points:
        west, south = anchor.lon, anchor.lat
        count = sum(1 for p in points if west <= p.lon <= west + lon_deg and south <= p.lat <= south + lat_deg)
        if count > best:
            best = count
            where = (west + lon_deg / 2, south + lat_deg / 2)
    return best, where


def _fetch(park: str) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{park.replace(' ', '_').lower()}.json"
    if cached.exists():
        return json.loads(cached.read_text())["features"]

    query = urllib.parse.urlencode(
        {
            "where": f"Facility='{park}'",
            "outFields": "Sub_Asset,Facility,Public_",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultRecordCount": "2000",
        }
    )
    with urllib.request.urlopen(f"{FACILITIES_URL}/query?{query}", timeout=120) as raw:
        body = json.loads(raw.read())
    if "error" in body:
        raise RuntimeError(body["error"])
    cached.write_text(json.dumps(body))
    return body["features"]


def load() -> list[Point]:
    points: list[Point] = []
    for park in PARKS:
        for feature in _fetch(park):
            geometry = feature.get("geometry") or {}
            if geometry.get("x") is None or geometry.get("y") is None:
                continue
            points.append(
                Point(
                    lon=float(geometry["x"]),
                    lat=float(geometry["y"]),
                    sub_asset=(feature["attributes"].get("Sub_Asset") or "Unknown"),
                    park=park,
                )
            )
    return points


def main() -> None:
    points = load()
    print(f"{len(points)} facility points across {len(PARKS)} parks\n")

    water = [p for p in points if p.sub_asset in WATER]
    toilets = [p for p in points if p.sub_asset in TOILETS]
    amenities = [p for p in points if p.sub_asset in AMENITIES]

    for park in PARKS:
        here = [p for p in points if p.park == park]
        print(f"{park}: {len(here)} rows")
        for label, subset in (
            ("water (the decisions table's safety kind)", WATER),
            ("toilets (#936's wider reading)", TOILETS),
            ("amenities OurHike has a pin for", AMENITIES),
        ):
            rows = [p for p in here if p.sub_asset in subset]
            print(f"  {label}: {len(rows)}")
            counts: dict[str, int] = {}
            for p in rows:
                counts[p.sub_asset] = counts.get(p.sub_asset, 0) + 1
            for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                print(f"      {name}: {n}")
        print()

    # What the classification did NOT claim, printed so the choice is auditable
    # rather than trusted: a reader can see every type that was left out.
    unclassified: dict[str, int] = {}
    for p in points:
        if p.sub_asset in WATER or p.sub_asset in TOILETS or p.sub_asset in AMENITIES:
            continue
        unclassified[p.sub_asset] = unclassified.get(p.sub_asset, 0) + 1
    print(f"not classified as either ({sum(unclassified.values())} rows):")
    for name, n in sorted(unclassified.items(), key=lambda kv: (-kv[1], name)):
        print(f"  {name}: {n}")
    print()

    latitude = sum(p.lat for p in points) / len(points)
    lon_deg, lat_deg = viewport_degrees(latitude)
    m_per_px = metres_per_pixel(latitude)
    print(
        f"a {VIEWPORT_W_PX} x {VIEWPORT_H_PX} phone map at z{ZOOM}, "
        f"lat {latitude:.2f}: {m_per_px:.2f} m/px, "
        f"{VIEWPORT_W_PX * m_per_px / 1000:.2f} x {VIEWPORT_H_PX * m_per_px / 1000:.2f} km"
    )

    for label, subset in (
        ("water only", water),
        ("water + toilets", water + toilets),
        ("amenities", amenities),
        ("everything OurHike would draw", water + toilets + amenities),
    ):
        best, where = densest_window(subset, lon_deg, lat_deg)
        centre = "" if where is None else f" centred near {where[1]:.4f}, {where[0]:.4f}"
        print(f"  densest z{ZOOM} screen, {label}: {best} of {len(subset)}{centre}")


if __name__ == "__main__":
    main()
