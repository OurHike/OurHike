"""Flag which ATC shelters/campsites have a nearby water source.

ATC's own data has no water-source layer at all (a confirmed gap - see
FEATURES.md). opentrail.org's crowd-sourced waypoints do tag water, and
often combine multiple attributes onto a single point via its `icons`
field (e.g. Cable Gap Shelter is a single opentrail point with
icons="cw" - shelter and water at the same spot, confirmed ~4m from
ATC's own coordinates for the same shelter).

For each ATC shelter/campsite, this checks for a water signal within a
small radius (default 150m - tight enough to avoid false matches at trail
junctions, loose enough to cover GPS variance and "spring is just off the
side trail" cases):
  1. Does the nearest matching opentrail point's own `icons` string contain
     "w" (combined-point case, like Cable Gap)?
  2. Is there a separate opentrail point tagged icon "w" within radius
     (standalone water source case)?
Either counts as "has water". This is a heuristic over crowd-sourced data,
not a verified/authoritative source - treat the output as a starting point
for a maintainer to confirm, not a final answer (value #4).
"""
import json
from pathlib import Path

import duckdb

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_DIR = Path(__file__).parent / "data" / "processed"
RADIUS_METERS = 150

PROJECTED_CRS = "EPSG:5070"
GEOGRAPHIC_CRS = "EPSG:4326"


def main():
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    for layer in ("shelters", "campsites"):
        con.execute(f"CREATE OR REPLACE TABLE {layer} AS SELECT * FROM ST_Read('{RAW_DIR / f'{layer}.geojson'}')")
    con.execute("CREATE OR REPLACE TABLE atc_sites AS SELECT Name, 'shelter' AS type, geom FROM shelters UNION ALL SELECT Name, 'campsite' AS type, geom FROM campsites")

    con.execute(f"CREATE OR REPLACE TABLE opentrail AS SELECT * FROM ST_Read('{RAW_DIR / 'opentrail_at.geojson'}')")

    con.execute(f"""
        CREATE OR REPLACE TABLE atc_sites_m AS
        SELECT Name, type, ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS geom_m, geom
        FROM atc_sites
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE opentrail_m AS
        SELECT title, icon, icons, dbid, ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true) AS geom_m
        FROM opentrail
    """)

    results = con.execute(f"""
        SELECT
            a.Name,
            a.type,
            ST_X(a.geom) AS lon,
            ST_Y(a.geom) AS lat,
            bool_or(o.icons LIKE '%w%') AS has_water,
            bool_or(o.icon = 'w') AS standalone_water_nearby,
            array_agg(DISTINCT o.title) FILTER (WHERE o.dbid IS NOT NULL) AS nearby_opentrail_points
        FROM atc_sites_m a
        LEFT JOIN opentrail_m o
            ON ST_Distance(a.geom_m, o.geom_m) <= {RADIUS_METERS}
        GROUP BY a.Name, a.type, a.geom
    """).fetchall()

    cols = ["name", "type", "lon", "lat", "has_water", "standalone_water_nearby", "nearby_opentrail_points"]
    records = [dict(zip(cols, row)) for row in results]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "shelter_campsite_water.json"
    out_path.write_text(json.dumps(records, indent=2, default=str))

    total = len(records)
    with_water = sum(1 for r in records if r["has_water"])
    shelters_total = sum(1 for r in records if r["type"] == "shelter")
    shelters_water = sum(1 for r in records if r["type"] == "shelter" and r["has_water"])
    campsites_total = sum(1 for r in records if r["type"] == "campsite")
    campsites_water = sum(1 for r in records if r["type"] == "campsite" and r["has_water"])

    print(f"{total} ATC shelters/campsites checked within {RADIUS_METERS}m of an opentrail point.")
    print(f"  shelters:  {shelters_water}/{shelters_total} flagged as having water nearby")
    print(f"  campsites: {campsites_water}/{campsites_total} flagged as having water nearby")
    print(f"  overall:   {with_water}/{total}")
    print(f"Output -> {out_path}")


if __name__ == "__main__":
    main()
