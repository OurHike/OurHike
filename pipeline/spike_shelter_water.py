"""Measure USGS NHD water features near every A.T. shelter (#529).

The issue: 97% of the 280 official shelters have no mapped water source
within 250 m, while nearly every shelter has water in reality. #97 measured
NHD against the *centerline* (841 true flowline crossings); this spike
measures it against the *shelters*, which is the frame #529 needs - "is
there NHD water where hikers sleep", per feature class, at the same radii
the issue and its OSM measurements use.

For each shelter (NPS ANST_Facilities layer 4), query the NHDPlus_HR
MapServer within a ~300 m envelope, compute a true minimum point-to-geometry
distance locally, and report coverage at 15/30/60/100/250 m radii. Feature
classes are kept separate because they make different claims to a hiker:

  spring        NHDPoint fcode 45800 (Spring/Seep)
  perennial     flowline fcode 46006
  intermittent  flowline fcode 46003 (ephemeral 46007 kept apart)
  artificial    flowline ftype 558 (artificial path through a waterbody)
  lakepond      NHDWaterbody ftype 390
  swampmarsh    NHDWaterbody ftype 466

Where no perennial flowline lands in the envelope, the search widens (1.2 km,
then 5 km, fcode-filtered) so distance statistics are real distances rather
than "not within 300 m". Every service response is cached on disk, so an
interrupted run resumes without re-paying the network, and a re-run makes no
network calls at all. WATER_SOURCES.md holds the findings; stdlib + requests
only, same as fetch_opentrail.py.
"""

import hashlib
import json
import math
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

OUT_DIR = os.environ.get("OUT_DIR", "data/spike")
CACHE_DIR = os.path.join(OUT_DIR, "nhd_cache")
RESULTS_PATH = os.path.join(OUT_DIR, "nhd_shelter_water_results.json")

SHELTERS_URL = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/4/query"
HR = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer"
NHD = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer"

# (key, url, geometry kind) - layer ids verified against each service's
# ?f=json listing on 2026-08-13: HR 2=NHDPoint, 3=NetworkNHDFlowline,
# 4=NonNetworkNHDFlowline, 9=NHDWaterbody; nhd 0=Point.
LAYERS = [
    ("hr_point", f"{HR}/2/query", "point"),
    ("hr_flow_net", f"{HR}/3/query", "line"),
    ("hr_flow_non", f"{HR}/4/query", "line"),
    ("hr_wb", f"{HR}/9/query", "polygon"),
    ("nhd_point", f"{NHD}/0/query", "point"),
]

RADII = [15, 30, 60, 100, 250]
ENV_M = 300.0  # half-width of the per-shelter query envelope, metres
M_PER_DEG_LAT = 111_132.0

# The two baselines this measurement exists to be compared against, both
# recorded on #529: the app's current supply (174 opentrail points), and the
# prior session's OSM point-source measurement (n=80, all New England).
BASELINE_CURRENT = {15: 0, 30: 1, 60: 3, 100: 4, 250: 8}
BASELINE_OSM_NE80 = {15: 0, 30: 1, 60: 5, 100: 6, 250: 8}

# The shelter layer's `State` column is a numeric code, ordered north to
# south along the trail (9 = WV has no official shelter). Decoded by
# matching each code's latitude range and per-state count against the
# trail's known shelter distribution.
STATE_CODES = {
    "0": "ME",
    "1": "NH",
    "2": "VT",
    "3": "MA",
    "4": "CT",
    "5": "NY",
    "6": "NJ",
    "7": "PA",
    "8": "MD",
    "9": "WV",
    "10": "VA",
    "11": "TN",
    "12": "NC",
    "13": "GA",
}

session = requests.Session()


def cache_key(url, params):
    blob = url + "|" + json.dumps(params, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()


def get_json(url, params, tries=5):
    """GET with retry/backoff and a disk cache. Raises on final failure."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, cache_key(url, params) + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    last = None
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, timeout=90)
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise RuntimeError(f"ArcGIS error: {j['error']}")
            with open(path, "w") as f:
                json.dump(j, f)
            return j
        except Exception as e:  # noqa: BLE001 - retry any transport/JSON error
            last = e
            time.sleep(2**attempt)
    raise RuntimeError(f"failed after {tries} tries: {url} :: {last}")


def fetch_shelters():
    feats, off = [], 0
    while True:
        j = get_json(
            SHELTERS_URL,
            {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "json",
                "resultOffset": off,
            },
        )
        fs = j.get("features", [])
        feats += fs
        if not j.get("exceededTransferLimit") or not fs:
            break
        off += len(fs)
    return feats


def envelope(lat, lon, half_m):
    dlat = half_m / M_PER_DEG_LAT
    dlon = half_m / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return {
        "xmin": lon - dlon,
        "ymin": lat - dlat,
        "xmax": lon + dlon,
        "ymax": lat + dlat,
        "spatialReference": {"wkid": 4326},
    }


def query_layer(url, lat, lon, half_m, where="1=1"):
    return get_json(
        url,
        {
            "geometry": json.dumps(envelope(lat, lon, half_m)),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "where": where,
            "outFields": "fcode,ftype,gnis_name,permanent_identifier",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "json",
        },
    )


# ---- local geometry: equirectangular metres around the shelter ----------


def to_xy(lat0, lon0):
    mx = M_PER_DEG_LAT * math.cos(math.radians(lat0))

    def f(lon, lat):
        return ((lon - lon0) * mx, (lat - lat0) * M_PER_DEG_LAT)

    return f


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_to_paths(proj, paths):
    """Min distance from the origin (the shelter) to a list of coordinate paths."""
    best = math.inf
    for path in paths:
        pts = [proj(x, y) for x, y in path]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            d = seg_dist(0.0, 0.0, ax, ay, bx, by)
            if d < best:
                best = d
    return best


def point_in_rings(proj, rings):
    inside = False
    for ring in rings:
        pts = [proj(x, y) for x, y in ring]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            if (ay > 0) != (by > 0):
                xint = ax + (0 - ay) / (by - ay) * (bx - ax)
                if xint > 0:
                    inside = not inside
    return inside


def feature_distance(lat0, lon0, geom, kind):
    proj = to_xy(lat0, lon0)
    if kind == "point":
        x, y = proj(geom["x"], geom["y"])
        return math.hypot(x, y)
    if kind == "line":
        return dist_to_paths(proj, geom.get("paths", []))
    rings = geom.get("rings", [])
    if point_in_rings(proj, rings):
        return 0.0
    return dist_to_paths(proj, rings)


# ---- classification -----------------------------------------------------


def classify(layer_key, attrs):
    a = {k.lower(): v for k, v in attrs.items()}
    fcode = a.get("fcode")
    ftype = a.get("ftype")
    if layer_key in ("hr_point", "nhd_point"):
        pref = "spring" if layer_key == "hr_point" else "nhd_spring"
        if fcode == 45800:
            return pref
        return pref + "_other"
    if layer_key in ("hr_flow_net", "hr_flow_non"):
        if fcode == 46006:
            return "perennial"
        if fcode == 46003:
            return "intermittent"
        if fcode == 46007:
            return "ephemeral"
        if ftype == 558:
            return "artificial"
        return "other_flowline"
    if layer_key == "hr_wb":
        if ftype == 390:
            return "lakepond"
        if ftype == 466:
            return "swampmarsh"
        return "other_waterbody"
    return "unknown"


# any-water = nearest of everything NHDPlus_HR knows about (springs, all
# flowlines including artificial paths, all waterbodies). The nhd MapServer
# point layer is kept out so any_water stays one service's claim.
ANY_CLASSES = [
    "spring",
    "perennial",
    "intermittent",
    "ephemeral",
    "artificial",
    "other_flowline",
    "lakepond",
    "swampmarsh",
    "other_waterbody",
]


def measure_shelter(sh):
    """Return per-class nearest features for one shelter."""
    lat, lon = sh["lat"], sh["lon"]
    nearest = {}  # class -> dict(dist_m, gnis_name, fcode, layer)
    errors = []
    for key, url, kind in LAYERS:
        try:
            j = query_layer(url, lat, lon, ENV_M)
        except RuntimeError as e:
            errors.append({"layer": key, "error": str(e)})
            continue
        for f in j.get("features", []):
            geom = f.get("geometry")
            if not geom:
                continue
            cls = classify(key, f["attributes"])
            d = feature_distance(lat, lon, geom, kind)
            cur = nearest.get(cls)
            if cur is None or d < cur["dist_m"]:
                a = {k.lower(): v for k, v in f["attributes"].items()}
                nearest[cls] = {
                    "dist_m": round(d, 1),
                    "gnis_name": a.get("gnis_name"),
                    "fcode": a.get("fcode"),
                    "layer": key,
                }
    # Escalate for distance stats: if no perennial inside the 300 m envelope,
    # search wider with an fcode filter so the record cap is not hit.
    for half in (1200.0, 5000.0):
        if "perennial" in nearest and nearest["perennial"]["dist_m"] <= half / 4:
            break
        if "perennial" not in nearest or nearest["perennial"]["dist_m"] > ENV_M:
            for url in (f"{HR}/3/query", f"{HR}/4/query"):
                try:
                    j = query_layer(url, lat, lon, half, where="fcode=46006")
                except RuntimeError as e:
                    errors.append({"layer": f"escalate:{url}", "error": str(e)})
                    continue
                for f in j.get("features", []):
                    geom = f.get("geometry")
                    if not geom:
                        continue
                    d = feature_distance(lat, lon, geom, "line")
                    cur = nearest.get("perennial")
                    if cur is None or d < cur["dist_m"]:
                        a = {k.lower(): v for k, v in f["attributes"].items()}
                        nearest["perennial"] = {
                            "dist_m": round(d, 1),
                            "gnis_name": a.get("gnis_name"),
                            "fcode": a.get("fcode"),
                            "layer": "escalated",
                        }
        if "perennial" in nearest:
            break
    return nearest, errors


# ---- reporting ----------------------------------------------------------


def coverage(rows, classes, r):
    return sum(1 for s in rows if any(c in s["nearest"] and s["nearest"][c]["dist_m"] <= r for c in classes))


def report(out):
    sh = out["shelters"]
    n = len(sh)
    classes = ["spring", "perennial", "intermittent", "artificial", "lakepond", "swampmarsh"]
    print(f"\ncoverage of shelters with >=1 feature within radius (n={n}):")
    print("radius | " + " | ".join(classes) + " | flowing(per+int) | any_water | current | OSM NE n=80")
    for r in RADII:
        row = [f"{100 * coverage(sh, [c], r) / n:.0f}%" for c in classes]
        flow = coverage(sh, ["perennial", "intermittent"], r)
        anyk = sum(1 for s in sh if s["any_water_m"] is not None and s["any_water_m"] <= r)
        print(
            f"{r:>4} m | "
            + " | ".join(row)
            + f" | {100 * flow / n:.0f}% | {100 * anyk / n:.0f}%"
            + f" | {BASELINE_CURRENT[r]}% | {BASELINE_OSM_NE80[r]}%"
        )

    per = [s["nearest"]["perennial"]["dist_m"] for s in sh if "perennial" in s["nearest"]]
    print(f"\nperennial flowline within 5 km: {len(per)} of {n}")
    print(f"  median {statistics.median(per):.0f} m, p90 {statistics.quantiles(per, n=10)[8]:.0f} m")
    anyw = [s["any_water_m"] for s in sh if s["any_water_m"] is not None]
    print(f"any NHD water inside the 300 m envelope: {len(anyw)} of {n}; median of those {statistics.median(anyw):.0f} m")

    ordered = sorted(sh, key=lambda s: s["lat"])
    thirds = [ordered[: n // 3], ordered[n // 3 : 2 * n // 3], ordered[2 * n // 3 :]]
    print("\nby latitude third, coverage within 250 m:")
    for name, t in zip(["south", "mid", "north"], thirds):
        row = [f"{c}:{100 * coverage(t, [c], 250) / len(t):.0f}%" for c in classes]
        anyk = sum(1 for s in t if s["any_water_m"] is not None and s["any_water_m"] <= 250)
        print(
            f"  {name} lat {t[0]['lat']:.1f}-{t[-1]['lat']:.1f} n={len(t)}: " + " ".join(row) + f" any:{100 * anyk / len(t):.0f}%"
        )

    within = [s["nearest"]["perennial"] for s in sh if "perennial" in s["nearest"] and s["nearest"]["perennial"]["dist_m"] <= 250]
    named = sum(1 for v in within if v.get("gnis_name"))
    print(f"\nnearest perennial within 250 m: {len(within)} shelters; {named} of those streams carry a GNIS name")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            out = json.load(f)
        print(f"reusing {RESULTS_PATH} ({out['n_shelters']} shelters, {len(out['errors'])} errors)")
        report(out)
        return 0

    raw = fetch_shelters()
    shelters = [
        {
            "name": f["attributes"].get("Name"),
            "state": STATE_CODES.get(f["attributes"].get("State")),
            "lat": f["geometry"]["y"],
            "lon": f["geometry"]["x"],
        }
        for f in raw
    ]
    shelters.sort(key=lambda s: s["lat"])
    n = len(shelters)
    print(f"{n} shelters, lat {shelters[0]['lat']:.3f}..{shelters[-1]['lat']:.3f}")

    results = [None] * n
    all_errors = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(measure_shelter, s): i for i, s in enumerate(shelters)}
        done = 0
        for fut in as_completed(futs):
            i = futs[fut]
            nearest, errors = fut.result()
            results[i] = {**shelters[i], "nearest": nearest}
            for e in errors:
                all_errors.append({"shelter": shelters[i]["name"], **e})
            done += 1
            if done % 40 == 0:
                print(f"  {done}/{n}")

    for r in results:
        cands = [r["nearest"][c]["dist_m"] for c in ANY_CLASSES if c in r["nearest"]]
        r["any_water_m"] = min(cands) if cands else None

    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "n_shelters": n,
        "envelope_m": ENV_M,
        "errors": all_errors,
        "shelters": results,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"errors: {len(all_errors)}")
    print(f"wrote {RESULTS_PATH}")
    report(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
