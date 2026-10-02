"""step_osm_water: OSM's water points, in fetch_osm_water.py's shape, written to derived.osm_water for dbt to read back.

    python step_osm_water.py [--warehouse data/warehouse.duckdb] [--points <osm_water.geojson>]

pipeline/ELT.md's ledger rows PO03, PO06, PO08 and PO09, and "Python steps,
outside dbt".

A STAND-IN FOR AN EXTRACT THAT WAITS. OSM's water points are fetched data,
and fetched data is the extract's to land (decision 4). The extract for them
waits on #1652 — Download OSM's Geofabrik extracts at most once a month, into
a private raw bucket that outlives the 7-day Actions cache, because the
fourteen state extracts are gigabytes and the bucket is the maintainer's to
create; tests/test_extract_layout.py lists `osm_water` as not yet extracted
for that reason. Until it lands, the points reach the warehouse only here,
and only from a file named on the command line:

- `--points` (build_marts.py --fixtures): make_dbt_fixtures.py's points, so
  the reach, the gate and the dedupe run in CI on rows in exactly the shape
  fetch_osm_water.py writes;
- nothing: an empty table, which is a build with no OSM water, as a publish
  that did not fetch it is today (export_poi.py: "a run that did not ask for
  it exports opentrail's water points alone"). So a dbt build publishes no
  OSM water until #1652 lands the points. That is a hiker-facing gap at
  cutover, not a decision this file makes: the identity ledger holds 201
  live `osm_water` points (reference/poi_identity.json, counted 2026-10-02),
  the water today's export publishes from the same source.

`--points data/raw/osm_water.geojson` would land the file fetch_osm_water.py
writes today, which is the bridge a cutover before #1652 could choose; it is
not the default, because choosing it is choosing where fetched data lives.

One row per feature, in the file's order, with its properties as the file
holds them: a tag OSM does not carry is absent, never null, and
lib/poi_description.py's describe_water() reads absence as "nobody tagged
it", which is the only reading it may have.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SCHEMA = "derived"
TABLE = "osm_water"
#: Why a run without --points has no OSM water, as the step says it.
WAITS = (
    "no extract lands OSM water yet (#1652 — Download OSM's Geofabrik extracts at most once a month, "
    "into a private raw bucket that outlives the 7-day Actions cache)"
)


def read_points(path: Path) -> list[dict]:
    """The file's features, as fetch_osm_water.py's feature() writes them, in order."""
    return json.loads(path.read_text(encoding="utf-8")).get("features", [])


def write_osm_water(con: duckdb.DuckDBPyConnection, features: list[dict], loaded_at: datetime) -> int:
    """Replace derived.osm_water with one row per feature. Returns the row count."""
    con.execute(f"create schema if not exists {SCHEMA}")
    con.execute(f"""
        create or replace table {SCHEMA}.{TABLE} (
            feature_row integer,
            osm_id varchar,
            kind varchar,
            lon double,
            lat double,
            properties json,
            _loaded_at timestamptz
        )
    """)
    rows = []
    for row, feature in enumerate(features):
        properties = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        osm_id = properties.get("osm_id")
        rows.append(
            (
                row,
                None if osm_id is None else str(osm_id),
                properties.get("kind"),
                coordinates[0],
                coordinates[1],
                json.dumps(properties),
                loaded_at,
            )
        )
    # No features is an empty table, not an error: executemany refuses an empty list.
    if rows:
        con.executemany(f"insert into {SCHEMA}.{TABLE} values (?, ?, ?, ?, ?, ?, ?)", rows)
    return con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--points", type=Path, help="OSM water points in fetch_osm_water.py's GeoJSON shape")
    args = parser.parse_args(argv)

    if args.points is not None and not args.points.exists():
        raise SystemExit(f"{args.points} does not exist: name a file of OSM water points, or none for a build without them")
    features = read_points(args.points) if args.points is not None else []
    with duckdb.connect(str(args.warehouse)) as con:
        written = write_osm_water(con, features, datetime.now(UTC))
    origin = str(args.points) if args.points is not None else WAITS
    print(f"{SCHEMA}.{TABLE}: {written:,} OSM water points, from {origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
