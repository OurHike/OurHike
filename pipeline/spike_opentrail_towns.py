"""Measure opentrail.org's town points before deciding whether to publish them (#803).

`export_poi.py` reads opentrail's `icon` property and takes exactly two
tags - "w" (water) and "r" (resupply) - dropping the rest, among them "t".
The issue asks whether those town points should be published, and says the
deciding rests on three measurements nobody has taken. This takes them.

WHAT IT MEASURES, and why each one can change the answer:

1. **How many town points there are, and what they are called.** The count
   in pipeline/README.md ("103 towns") is quoted from a fetch nobody has
   repeated; a feed that has moved since is worth knowing about before
   anything is built on it.

2. **Overlap with ATC's 59 A.T. Communities**, which already publish as
   `resupply`. Publishing Damascus twice, at two confidences, with two ids,
   is worse than not publishing the second copy - the water layers already
   carry a MEASURED dedup radius (WATER_DEDUP_RADIUS_M) for exactly this
   shape of problem, and this needs its own number rather than a radius
   that sounds about right. Measured two ways, because they disagree:
   by distance, and by name.

3. **How far each town point sits from the trail**, which decides whether
   its projected mile means anything. `attach_miles` will happily project a
   town centroid onto the centreline and produce a number; that number
   means "where the trail passes closest to this town", not "where you
   leave the trail for it". A plan that hangs a day off the difference is a
   plan built on a measurement nobody made.

Distances are computed on the WGS84 sphere via DuckDB's spatial extension
(`ST_Distance_Sphere`), which is what the rest of this pipeline uses for
metre distances between points, and against the centreline as it is
published - not against the marker-calibrated axis, because the question
here is geometric ("how far off the line is this dot") rather than
positional ("what mile is it").

Everything is cached under OUT_DIR, so a re-run only re-reports. Findings
belong in pipeline/README.md beside the other source notes.

    .venv/Scripts/python spike_opentrail_towns.py
"""

import json
import os
import sys
from pathlib import Path

import duckdb

from lib.arcgis import fetch_layer_geojson
from lib.http_retry import request_with_retry

OUT_DIR = Path(os.environ.get("OUT_DIR", "data/spike"))
OPENTRAIL_URL = "https://opentrail.org/api/getData"
COMMUNITIES_URL = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/AT_Communities/FeatureServer/0"
CENTERLINE_URL = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0"

# The radii the overlap is counted at. Deliberately spanning three orders of
# magnitude: a town centroid and a Community centroid for the same town can
# be a block apart or a valley apart, and the point of the exercise is to
# find out which.
OVERLAP_RADII_M = [100, 250, 500, 1_000, 2_000, 5_000]

# The distances the off-trail question is counted at. 1 km is roughly the
# walk from a trailhead to a main street; 5 km is a hitch.
OFF_TRAIL_BANDS_M = [100, 500, 1_000, 2_000, 5_000, 10_000]

# WHAT A POINT IS CALLED, as a proxy for what it is.
#
# opentrail's `icon` legend in export_poi.py is explicitly "best-effort
# inferred from feature titles/counts - not documented by the API", so the
# only way to check the inference is to read the titles at scale. Keyword
# buckets are crude and that is the point: they are reproducible, and a
# result this lopsided does not need a subtle instrument. Names matching
# neither bucket are counted separately rather than assigned to one.
ROAD_WORDS = (
    "gap",
    "road",
    " rd",
    "rd ",
    "crossing",
    "highway",
    "hwy",
    "drive",
    "parkway",
    "pkwy",
    "route",
    " st ",
    "turnpike",
    "bridge",
    "parking",
    "trailhead",
    "trail head",
    "pike",
    "lane",
)
SERVICE_WORDS = (
    "hostel",
    "store",
    "grocer",
    "outfitter",
    "inn",
    "motel",
    "hotel",
    "restaurant",
    "cafe",
    "market",
    "resupply",
    "deli",
    "bakery",
    "lodg",
    "campground",
    "shuttle",
    "laundry",
    "post office",
    "visitor",
    "pizza",
    "diner",
    "food",
    "farm",
    "b&b",
    "bunk",
    "hiker",
)


def name_bucket(name: str) -> str:
    text = " " + (name or "").lower() + " "
    road = any(word in text for word in ROAD_WORDS)
    service = any(word in text for word in SERVICE_WORDS)
    if service and not road:
        return "service"
    if road and not service:
        return "road"
    if road and service:
        return "both"
    return "neither"


def cached(name: str, fetch):
    """Fetch once, then re-read. An interrupted run resumes; a re-run only
    re-reports, which is what makes the numbers below quotable rather than
    re-derived slightly differently each time."""
    path = OUT_DIR / name
    if path.exists():
        return json.loads(path.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = fetch()
    path.write_text(json.dumps(data))
    return data


def fetch_opentrail() -> dict:
    resp = request_with_retry(OPENTRAIL_URL, params={"trail": "AT"}, timeout=60)
    return resp.json()


def opentrail_points(raw: dict) -> list[dict]:
    """The feed's features, flattened to what this measurement needs.

    Tolerant about the envelope on purpose: this is a third-party feed with
    no schema promise, and a spike that dies on an unexpected wrapper tells
    you nothing about the data inside it.
    """
    features = raw.get("features") if isinstance(raw, dict) else None
    if features is None and isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, dict) and isinstance(value.get("features"), list):
                features = value["features"]
                break
    if not isinstance(features, list):
        return []

    points = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            continue
        points.append(
            {
                "icon": props.get("icon"),
                "name": props.get("title") or props.get("name") or "",
                "lon": float(coords[0]),
                "lat": float(coords[1]),
            }
        )
    return points


def normalised(name: str | None) -> str:
    """A town name reduced to what two sources are likely to agree on.

    "Damascus, VA", "Damascus" and "DAMASCUS TOWN OF" all have to match, and
    ATC's own layer carries entries like "Unicoi County" - so the state
    suffix, the punctuation and the administrative nouns come off.
    """
    text = (name or "").lower()
    for suffix in (" county", " town of", " city of", " borough", " township"):
        text = text.replace(suffix, " ")
    keep = [c if c.isalnum() else " " for c in text]
    words = "".join(keep).split()
    # A trailing two-letter state code is a suffix, not part of the name.
    if len(words) > 1 and len(words[-1]) == 2:
        words = words[:-1]
    return " ".join(words)


def main() -> int:
    raw = cached("opentrail_at.json", fetch_opentrail)
    points = opentrail_points(raw)
    if not points:
        print("no points parsed from the opentrail feed - envelope changed?")
        return 1

    by_icon: dict[str, int] = {}
    for point in points:
        by_icon[str(point["icon"])] = by_icon.get(str(point["icon"]), 0) + 1

    print(f"opentrail feed: {len(points)} points")
    for icon, count in sorted(by_icon.items(), key=lambda kv: -kv[1]):
        print(f"  {icon!r:>6}: {count}")

    # --- 0. what the tags actually hold ------------------------------------
    print("\nwhat each tag's points are CALLED (export_poi.py's legend is a guess):")
    for icon in ("t", "r", "j", "o", "w"):
        named = [p["name"] for p in points if p["icon"] == icon]
        if not named:
            continue
        buckets: dict[str, int] = {}
        for name in named:
            key = name_bucket(name)
            buckets[key] = buckets.get(key, 0) + 1
        summary = "  ".join(
            f"{key} {count:>3} ({count / len(named) * 100:.0f}%)" for key, count in sorted(buckets.items(), key=lambda kv: -kv[1])
        )
        print(f"  {icon!r} n={len(named):<5} {summary}")

    towns = [p for p in points if p["icon"] == "t"]
    resupply = [p for p in points if p["icon"] == "r"]
    print(f"\ntowns ('t'): {len(towns)}   resupply ('r'): {len(resupply)}")
    if not towns:
        print("nothing tagged 't' - the premise of #803 no longer holds")
        return 0

    # The check that decides whether the EXISTING mapping is sound: the
    # export publishes every "r" point as resupply at high confidence.
    service_r = [p for p in resupply if name_bucket(p["name"]) in ("service", "both")]
    print(f"\n'r' points whose name suggests a store, hostel or outfitter: {len(service_r)} of {len(resupply)}")
    if not service_r:
        print("  none at all. The 15 that are not road-named:")
        for point in resupply:
            if name_bucket(point["name"]) == "neither":
                print(f"    {point['name']!r}")

    communities = cached("atc_communities.json", lambda: fetch_layer_geojson(COMMUNITIES_URL))["features"]
    print(f"A.T. Communities: {len(communities)}")

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("CREATE TABLE town (name TEXT, norm TEXT, lon DOUBLE, lat DOUBLE)")
    con.executemany(
        "INSERT INTO town VALUES (?, ?, ?, ?)",
        [(t["name"], normalised(t["name"]), t["lon"], t["lat"]) for t in towns],
    )
    con.execute("CREATE TABLE community (name TEXT, norm TEXT, lon DOUBLE, lat DOUBLE)")
    con.executemany(
        "INSERT INTO community VALUES (?, ?, ?, ?)",
        [
            (
                (c.get("properties") or {}).get("NAME") or "",
                normalised((c.get("properties") or {}).get("NAME")),
                float((c.get("geometry") or {}).get("coordinates", [0, 0])[0]),
                float((c.get("geometry") or {}).get("coordinates", [0, 0])[1]),
            )
            for c in communities
            if (c.get("geometry") or {}).get("type") == "Point"
        ],
    )

    # --- 2. overlap, by distance and by name -------------------------------
    nearest = con.execute(
        """
        SELECT t.name, t.norm,
               MIN(ST_Distance_Sphere(ST_Point(t.lon, t.lat), ST_Point(c.lon, c.lat)))
        FROM town t CROSS JOIN community c
        GROUP BY t.name, t.norm
        """
    ).fetchall()
    print("\noverlap with the 59 Communities, by distance:")
    for radius in OVERLAP_RADII_M:
        hits = sum(1 for _, _, d in nearest if d is not None and d <= radius)
        print(f"  within {radius:>6} m: {hits:>3} of {len(towns)}")

    community_names = {row[0] for row in con.execute("SELECT norm FROM community").fetchall()}
    by_name = [t for t in towns if normalised(t["name"]) in community_names]
    print(f"\noverlap by NAME: {len(by_name)} of {len(towns)}")
    for town in sorted(by_name, key=lambda t: t["name"])[:12]:
        distance = next(d for n, _, d in nearest if n == town["name"])
        print(f"  {town['name']:<34} nearest Community {distance / 1000:.1f} km")
    if len(by_name) > 12:
        print(f"  … and {len(by_name) - 12} more")

    # --- 3. how far off the trail a town point sits ------------------------
    centerline = cached("atc_centerline.json", lambda: fetch_layer_geojson(CENTERLINE_URL))["features"]
    print(f"\ncentreline: {len(centerline)} features")
    con.execute("CREATE TABLE line (geom GEOMETRY)")
    con.executemany(
        "INSERT INTO line VALUES (ST_GeomFromGeoJSON(?))",
        [
            (json.dumps(f["geometry"]),)
            for f in centerline
            if (f.get("geometry") or {}).get("type") in ("LineString", "MultiLineString")
        ],
    )

    # Degrees, then metres at this latitude. ST_Distance_Sphere does not take
    # a line, so the nearest point on the line is found in planar degrees
    # first - fine over the hundred metres to a few kilometres this is
    # measuring, and stated here rather than assumed.
    off_trail = con.execute(
        """
        WITH nearest AS (
          SELECT t.name AS name, t.lon AS lon, t.lat AS lat,
                 MIN(ST_Distance(ST_Point(t.lon, t.lat), l.geom)) AS deg
          FROM town t CROSS JOIN line l
          GROUP BY t.name, t.lon, t.lat
        )
        SELECT name, deg * 111320.0 * COS(RADIANS(lat)) AS approx_m, deg * 111320.0 AS ns_m
        FROM nearest
        """
    ).fetchall()
    # The conservative reading of the two axes: a distance is at least the
    # smaller of them, so the SMALLER is used and the count of "close" towns
    # can only be generous. Erring that way is deliberate - it makes the
    # case for publishing look better than it is, so a negative result is
    # trustworthy.
    distances = sorted(min(a, b) for _, a, b in off_trail)
    print("\nhow far a town point sits from the published centreline:")
    for band in OFF_TRAIL_BANDS_M:
        hits = sum(1 for d in distances if d <= band)
        print(f"  within {band:>6} m: {hits:>3} of {len(distances)}")
    if distances:
        median = distances[len(distances) // 2]
        print(f"  median {median / 1000:.2f} km · worst {distances[-1] / 1000:.1f} km")

    print("\nfurthest ten, which are the ones a published mile would misdescribe:")
    for name, a, b in sorted(off_trail, key=lambda r: -min(r[1], r[2]))[:10]:
        print(f"  {name:<34} {min(a, b) / 1000:>6.1f} km")

    return 0


if __name__ == "__main__":
    sys.exit(main())
