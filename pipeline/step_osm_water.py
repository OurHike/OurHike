"""step_osm_water: OSM's water points, in fetch_osm_water.py's shape, written to derived.osm_water for dbt to read back.

    python step_osm_water.py [--warehouse data/warehouse.duckdb] [--points <osm_water.geojson>]
    python step_osm_water.py --landed <osm_water.geojson>      # build_marts.py --lane monthly

pipeline/ELT.md's ledger rows PO03, PO06, PO08 and PO09, and "Python steps,
outside dbt".

THE POINTS ARE A SCAN OF THE EXTRACTS THE MONTHLY LANE KEEPS (#1652 —
Download OSM's Geofabrik extracts at most once a month, into a private raw
bucket that outlives the 7-day Actions cache). The fourteen state extracts
are fetched data, and fetched data is the extract's to land (decision 4):
extract/_shared/osm/geofabrik.py keeps them in the raw store, monthly, with
one manifest row each, and never hands their bytes to dlt. They are files, so
the water in them is read in refresh-reference.yml's pin job:
extract/_geofabrik.py's `pull` puts the copies in data/raw/osm/,
fetch_osm_water.py scans them for point sources, unchanged, and the file it
writes is pinned with the run's raw inputs as `derived/osm_water.geojson`,
which build-reference.yml's build reads back from the pin.
This step lands that file, in one of three ways:

- `--landed` (build_marts.py --lane monthly): the pinned scan, under
  data/raw/derived/. A run whose extracts were missing or unreadable
  pinned the last landed scan in its place, so the points are last month's
  rather than none. A file that is absent means no scan has ever landed (a
  pin before the extract's first complete set): the step warns and lands
  an empty table, a build with no OSM water, as before #1652;
- `--points` (build_marts.py --fixtures): make_dbt_fixtures.py's points, so
  the reach, the gate and the dedupe run in CI on rows in exactly the shape
  fetch_osm_water.py writes. Absent is an error here, because a fixture that
  is missing is a broken fixture;
- neither: an empty table, which is a build with no OSM water, as a publish
  that did not fetch it is today (export_poi.py: "a run that did not ask for
  it exports opentrail's water points alone").

Monthly run 13 (refresh-reference.yml 37182708502, 2026-10-04) landed none,
where the identity ledger holds 201 live `osm_water` points
(reference/poi_identity.json, counted 2026-10-02): that is the gap the
`--landed` path closes, from the first monthly run whose extract lands all
fourteen copies.

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
#: Why a run with no points file has no OSM water, as the step says it.
WAITS = "no scan of OSM's Geofabrik extracts was named, so this build lands no OSM water"
#: Why a monthly build's --landed file is absent, as the step says it.
NEVER_LANDED = (
    "no scan of OSM's Geofabrik extracts has landed yet: the raw store holds no complete set of the fourteen "
    "copies, and no earlier build pinned one (extract/_geofabrik.py), so this build publishes no OSM water"
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
    named = parser.add_mutually_exclusive_group()
    named.add_argument("--points", type=Path, help="OSM water points in fetch_osm_water.py's GeoJSON shape")
    named.add_argument(
        "--landed",
        type=Path,
        help="the monthly build's pinned scan of the extracts; absent is a build with no OSM water, said in a warning",
    )
    args = parser.parse_args(argv)

    if args.points is not None and not args.points.exists():
        raise SystemExit(f"{args.points} does not exist: name a file of OSM water points, or none for a build without them")
    path, origin = args.points, WAITS
    if args.landed is not None:
        if args.landed.exists():
            path = args.landed
        else:
            origin = NEVER_LANDED
            print(f"::warning title=No OSM water this build::{NEVER_LANDED}")
    if path is not None:
        origin = str(path)
    features = read_points(path) if path is not None else []
    with duckdb.connect(str(args.warehouse)) as con:
        written = write_osm_water(con, features, datetime.now(UTC))
    print(f"{SCHEMA}.{TABLE}: {written:,} OSM water points, from {origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
