"""Census OSM water features against all 280 A.T. shelters (#529).

The OSM measurements recorded on #529 were Overpass-bound: 80 shelters, all
of them in New England, and a recommendation shaped by that bias. This is
the full census those comments said the question wants - every shelter,
every trail state, from local Geofabrik extracts (the shape that works;
Overpass from this sandbox does not) - so OSM and NHD (spike_shelter_water)
can be compared on identical footing.

Point sources use the same clause set as the prior measurements, so results
are comparable: natural=spring, amenity=drinking_water, man_made=water_tap,
man_made=water_well. Water ways (natural=water polygons, waterway=stream/
river lines) are measured by nearest *node*, an approximation that can only
overstate the distance to a polygon interior - stated wherever those numbers
are quoted. The trail rides the NC/TN state line for ~200 miles, so each
extract is measured for its own state's shelters plus the neighbouring
trail states', and every shelter takes the minimum over all extracts that
could serve it.

DuckDB does the heavy lifting: st_readosm reads each .osm.pbf directly, the
per-extract scan is clipped to the bounding box of the shelters it serves,
and distances come from a range join - the big mid-Atlantic extracts never
land in Python memory. Extracts (~2 GB total) and intermediate parquet are
cached in OUT_DIR, so an interrupted run resumes where it stopped and a
re-run only re-reports. WATER_SOURCES.md holds the findings.
"""

import json
import math
import os
import subprocess
import sys

import duckdb

from spike_shelter_water import STATE_CODES
from spike_shelter_water import fetch_shelters as fetch_shelters_raw

OUT_DIR = os.environ.get("OUT_DIR", "data/spike")
RESULTS_PATH = os.path.join(OUT_DIR, "osm_census_water_results.json")
GEOFABRIK = "https://download.geofabrik.de/north-america/us"
RADII = [15, 30, 60, 100, 250]
M_PER_DEG_LAT = 111_132.0

# extract -> shelter states whose water could sit inside that extract
EXTRACT_SERVES = {
    "georgia": ["GA", "NC"],
    "north-carolina": ["GA", "NC", "TN"],
    "tennessee": ["NC", "TN", "VA"],
    "virginia": ["TN", "VA", "WV"],
    "west-virginia": ["VA", "WV", "MD"],
    "maryland": ["WV", "MD", "PA", "VA"],
    "pennsylvania": ["MD", "PA", "NJ"],
    "new-jersey": ["PA", "NJ", "NY"],
    "new-york": ["NJ", "NY", "CT"],
    "connecticut": ["NY", "CT", "MA"],
    "massachusetts": ["CT", "MA", "VT"],
    "vermont": ["MA", "VT", "NH"],
    "new-hampshire": ["VT", "NH", "ME"],
    "maine": ["NH", "ME"],
}

REGIONS = [
    ("south (GA/NC/TN)", ("GA", "NC", "TN")),
    ("mid (VA-NY)", ("VA", "WV", "MD", "PA", "NJ", "NY")),
    ("New England", ("CT", "MA", "VT", "NH", "ME")),
]

POINT_CLAUSE = """
    tags['natural'] = 'spring'
    OR tags['amenity'] = 'drinking_water'
    OR tags['man_made'] IN ('water_tap', 'water_well')
"""
WAY_CLASS = """
    CASE
        WHEN tags['natural'] = 'water' THEN 'natural_water'
        WHEN tags['waterway'] = 'stream' THEN 'waterway_stream'
        WHEN tags['waterway'] = 'river' THEN 'waterway_river'
    END
"""


def ensure_pbf(state):
    path = os.path.join(OUT_DIR, f"{state}-latest.osm.pbf")
    if not os.path.exists(path):
        print(f"downloading {state}...", flush=True)
        subprocess.run(
            ["curl", "-sSL", "-o", path, f"{GEOFABRIK}/{state}-latest.osm.pbf"],
            check=True,
        )
    return path


def extract_state(con, state, bbox):
    """Point-source nodes statewide; water-way nodes within the shelter bbox."""
    pbf = ensure_pbf(state)
    pts = os.path.join(OUT_DIR, f"osm_pts_{state}.parquet")
    if not os.path.exists(pts):
        con.execute(f"""
            COPY (
                SELECT id, lat, lon,
                       CASE
                           WHEN tags['natural'] = 'spring' THEN 'spring'
                           WHEN tags['amenity'] = 'drinking_water' THEN 'drinking_water'
                           WHEN tags['man_made'] = 'water_tap' THEN 'water_tap'
                           ELSE 'water_well'
                       END AS cls,
                       tags['seasonal'] AS seasonal,
                       tags['intermittent'] AS intermittent,
                       tags['drinking_water'] AS drinking_water_tag,
                       tags['name'] AS name
                FROM st_readosm('{pbf}')
                WHERE kind = 'node' AND tags IS NOT NULL AND ({POINT_CLAUSE})
            ) TO '{pts}'
        """)
    wnodes = os.path.join(OUT_DIR, f"osm_waynodes_{state}.parquet")
    if not os.path.exists(wnodes):
        con.execute(f"""
            CREATE OR REPLACE TABLE ways AS
            SELECT id, refs, {WAY_CLASS} AS cls,
                   tags['seasonal'] AS seasonal,
                   tags['intermittent'] AS intermittent
            FROM st_readosm('{pbf}')
            WHERE kind = 'way' AND tags IS NOT NULL AND ({WAY_CLASS}) IS NOT NULL
        """)
        con.execute(f"""
            CREATE OR REPLACE TABLE bbox_nodes AS
            SELECT id, lat, lon FROM st_readosm('{pbf}')
            WHERE kind = 'node'
              AND lat BETWEEN {bbox[0]} AND {bbox[1]}
              AND lon BETWEEN {bbox[2]} AND {bbox[3]}
        """)
        con.execute(f"""
            COPY (
                WITH wn AS (
                    SELECT id AS way_id, cls, seasonal, intermittent,
                           unnest(refs) AS ref
                    FROM ways
                )
                SELECT wn.way_id, wn.cls, wn.seasonal, wn.intermittent,
                       n.lat, n.lon
                FROM wn JOIN bbox_nodes n ON n.id = wn.ref
            ) TO '{wnodes}'
        """)
        con.execute("DROP TABLE IF EXISTS ways")
        con.execute("DROP TABLE IF EXISTS bbox_nodes")
    return pts, wnodes


def measure(shelters):
    con = duckdb.connect(os.path.join(OUT_DIR, "osm_census.duckdb"))
    con.execute("LOAD spatial")
    con.execute(f"SET temp_directory='{OUT_DIR}/duckdb_tmp'")

    pad = 350.0 / M_PER_DEG_LAT
    pts_files, wnode_files = [], []
    for state, serves in EXTRACT_SERVES.items():
        mine = [s for s in shelters if s["state"] in serves]
        if not mine:
            continue
        lats = [s["lat"] for s in mine]
        lons = [s["lon"] for s in mine]
        bbox = (min(lats) - pad, max(lats) + pad, min(lons) - pad * 1.4, max(lons) + pad * 1.4)
        print(f"extracting {state} (bbox for {len(mine)} shelters)...", flush=True)
        pts, wnodes = extract_state(con, state, bbox)
        pts_files.append(pts)
        wnode_files.append(wnodes)

    con.execute("CREATE OR REPLACE TABLE shelters (idx INT, state TEXT, name TEXT, lat DOUBLE, lon DOUBLE)")
    con.executemany(
        "INSERT INTO shelters VALUES (?, ?, ?, ?, ?)",
        [(i, s["state"], s["name"], s["lat"], s["lon"]) for i, s in enumerate(shelters)],
    )

    dist_expr = (
        f"sqrt(pow((p.lon - s.lon) * {M_PER_DEG_LAT} * cos(radians(s.lat)), 2) + pow((p.lat - s.lat) * {M_PER_DEG_LAT}, 2))"
    )
    pts_list = "', '".join(pts_files)
    point_rows = con.execute(f"""
        WITH pts AS (
            SELECT DISTINCT id, lat, lon, cls, seasonal, intermittent, drinking_water_tag, name
            FROM read_parquet(['{pts_list}'])
        )
        SELECT s.idx, p.cls, MIN({dist_expr}) AS d,
               arg_min(p.name, {dist_expr}) AS name,
               arg_min(p.seasonal, {dist_expr}) AS seasonal,
               arg_min(p.intermittent, {dist_expr}) AS intermittent
        FROM pts p
        JOIN shelters s
          ON p.lat BETWEEN s.lat - 0.003 AND s.lat + 0.003
         AND p.lon BETWEEN s.lon - 0.004 AND s.lon + 0.004
        GROUP BY 1, 2
    """).fetchall()

    wdist_expr = dist_expr.replace("p.", "w.")
    wn_list = "', '".join(wnode_files)
    way_rows = con.execute(f"""
        SELECT s.idx, w.cls, w.way_id, w.seasonal, w.intermittent, MIN({wdist_expr}) AS d
        FROM read_parquet(['{wn_list}']) w
        JOIN shelters s
          ON w.lat BETWEEN s.lat - 0.003 AND s.lat + 0.003
         AND w.lon BETWEEN s.lon - 0.004 AND s.lon + 0.004
        GROUP BY 1, 2, 3, 4, 5
        HAVING MIN({wdist_expr}) <= 300
    """).fetchall()

    by_idx_pts = {}
    for idx, cls, d, name, seas, inter in point_rows:
        by_idx_pts.setdefault(idx, {})[cls] = {
            "dist_m": round(d, 1),
            "name": name,
            "seasonal": seas,
            "intermittent": inter,
        }
    by_idx_ways = {}
    for idx, cls, way_id, seas, inter, d in way_rows:
        by_idx_ways.setdefault(idx, {}).setdefault(cls, []).append(
            {"way_id": way_id, "dist_m": round(d, 1), "seasonal": seas, "intermittent": inter}
        )
    results = []
    for i, s in enumerate(shelters):
        ways = {
            cls: {
                "count_250m": sum(1 for w in lst if w["dist_m"] <= 250),
                "min_dist_m": min(w["dist_m"] for w in lst),
            }
            for cls, lst in by_idx_ways.get(i, {}).items()
        }
        results.append({**s, "nearest_points": by_idx_pts.get(i, {}), "ways": ways})
    return results


def report(results):
    n = len(results)

    def cov(rows, r_m):
        return sum(1 for r in rows if any(v["dist_m"] <= r_m for v in r["nearest_points"].values()))

    print(f"\nOSM point-source coverage (n={n}):")
    print("region | " + " | ".join(f"{r} m" for r in RADII))
    print("whole trail | " + " | ".join(f"{100 * cov(results, r) / n:.0f}%" for r in RADII))
    for label, states in REGIONS:
        rows = [x for x in results if x["state"] in states]
        print(f"{label} (n={len(rows)}) | " + " | ".join(f"{100 * cov(rows, r) / len(rows):.0f}%" for r in RADII))

    print("\nby state, point sources / waterway=stream ways within 250 m:")
    seen = []
    for s in results:
        if s["state"] not in seen:
            seen.append(s["state"])
    for st in seen:
        rows = [r for r in results if r["state"] == st]
        k = cov(rows, 250)
        kw = sum(1 for r in rows if r["ways"].get("waterway_stream", {}).get("min_dist_m", math.inf) <= 250)
        print(f"  {st}: n={len(rows)} points {k} ({100 * k / len(rows):.0f}%)  streams {kw} ({100 * kw / len(rows):.0f}%)")

    near = [(c, v) for r in results for c, v in r["nearest_points"].items() if v["dist_m"] <= 250]
    by_cls = {}
    for c, _ in near:
        by_cls[c] = by_cls.get(c, 0) + 1
    tagged = sum(1 for _, v in near if v.get("seasonal") or v.get("intermittent"))
    named = sum(1 for _, v in near if v.get("name"))
    print(f"\nnearest-point classes within 250 m: {by_cls}")
    print(f"of those points: {named} named, {tagged} carrying seasonal/intermittent tags")
    for cls in ("waterway_stream", "natural_water"):
        k = sum(1 for r in results if r["ways"].get(cls, {}).get("min_dist_m", math.inf) <= 250)
        print(f"{cls} way within 250 m: {k} of {n} ({100 * k / n:.0f}%)")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            results = json.load(f)["shelters"]
        print(f"reusing {RESULTS_PATH} ({len(results)} shelters)")
        report(results)
        return 0

    raw = fetch_shelters_raw()
    shelters = [
        {
            "name": f["attributes"].get("Name"),
            "state": STATE_CODES.get(f["attributes"].get("State")),
            "lat": f["geometry"]["y"],
            "lon": f["geometry"]["x"],
        }
        for f in raw
    ]
    results = measure(shelters)
    with open(RESULTS_PATH, "w") as f:
        json.dump({"n_shelters": len(results), "shelters": results}, f, indent=1)
    print(f"wrote {RESULTS_PATH}")
    report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
