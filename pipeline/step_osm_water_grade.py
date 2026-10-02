"""step_osm_water_grade: the grade half of OSM water's reach, written to derived.osm_water_grade for dbt to read back.

    python step_osm_water_grade.py [--warehouse data/warehouse.duckdb]
        [--elevations <json>] [--previous <osm_water_reach.json>]

pipeline/ELT.md's ledger rows PO06 and PO07, and "Python steps, outside dbt".

THE DISTANCE HALF IS SQL, THE GRADE HALF IS THIS. build_osm_water_reach.py
judges each corridor OSM water point twice: within MATCH_RADIUS_FT (100 ft)
of the nearest centerline, side trail, published network trail, shelter or
campsite, which int_points_of_interest__osm_water_reach now measures; and,
for a point that passes, no steeper than MAX_GRADE (15%) between the water
and the feature it passed on, from USGS EPQS elevations at both ends, unless
the walk is shorter than MIN_GRADE_RUN_FT (10 ft). The second needs EPQS,
which answers one point at a time at about 1.9 s a point, so it is a step
between the dbt invocation that measures and the one that gates (Reasoned:
the read SQL cannot make, as for PO07's site water). The loop is
build_osm_water_reach.apply_grade_gate(), called rather than copied, so its
reasons, its "an unknown is not a pass" and its grade_floored mark are the
Python's; the gate inside it is fetch_trail_water.grade_gate(), the one home
of both water gates' grade.

THE WRITE GUARDS ARE build_osm_water_reach.write()'s: fewer than
MIN_REACHABLE (40) reachable points, or fewer than MAX_REACHABLE_DROP_RATIO
(50%) of `--previous`'s, writes nothing. They watch a scan that read no trail
geometry, and two cases have no scan to watch: `--elevations`
(build_marts.py --fixtures), whose few points are made to reach every
branch rather than to be a census; and a build in which no OSM water landed
at all (step_osm_water.py, until #1652), which has nothing to collapse.

One row per row of int_points_of_interest__osm_water_reach, so every corridor
point has a verdict: `reachable` is both gates, and an ungraded point is not
reachable (build_osm_water_reach.is_reachable()).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb

import build_osm_water_reach
import fetch_trail_water
from step_site_water import offline_elevations

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
REACH = "intermediate.int_points_of_interest__osm_water_reach"
POINTS = "derived.osm_water"
SCHEMA = "derived"
TABLE = "osm_water_grade"


def read_reach(con: duckdb.DuckDBPyConnection, relation: str = REACH) -> list[dict]:
    """The distance pass's rows as build_osm_water_reach.measure_distances() records them, by osm_id."""
    try:
        rows = con.execute(
            f"select osm_id, lon, lat, nearest, nearest_source, nearest_m, walk_lon, walk_lat, passes_distance, reason "
            f"from {relation} order by osm_id"
        ).fetchall()
    except duckdb.CatalogException as missing:
        raise SystemExit(
            f"{relation} is not in the warehouse: build `source:derived.osm_water+` with dbt first, "
            f"then run this step. ({missing})"
        ) from missing
    records = []
    for osm_id, lon, lat, nearest, nearest_source, nearest_m, walk_lon, walk_lat, passes, reason in rows:
        record = {"osm_id": osm_id, "lon": lon, "lat": lat, "nearest": nearest, "passes_distance": bool(passes)}
        if nearest_source is not None:
            record["nearest_source"] = nearest_source
        # measure_distances() keeps the distance at 2 dp, and the grade's run is read off that.
        record["nearest_m"] = None if nearest_m is None else float(nearest_m)
        if walk_lon is not None:
            record["walk_to"] = {"lon": walk_lon, "lat": walk_lat}
        if reason is not None:
            record["reason"] = reason
        records.append(record)
    return records


@contextlib.contextmanager
def _grading(elevations: Path | None):
    """apply_grade_gate() with its checkpoints kept out of data/raw, and EPQS read from a file when one is named.

    The checkpoints go beside build_osm_water_reach.OUT_PATH, which is the file
    that script resumes from: a partial written there by this step would be
    resumed by the script's next run. So OUT_PATH points into a folder that
    lives as long as the call.
    """
    live_out, live_elevation = build_osm_water_reach.OUT_PATH, build_osm_water_reach.elevation_ft
    with tempfile.TemporaryDirectory(prefix="step-osm-water-grade-") as folder:
        build_osm_water_reach.OUT_PATH = Path(folder) / "osm_water_reach.json"
        if elevations is not None:
            build_osm_water_reach.elevation_ft = offline_elevations(elevations)
        try:
            yield Path(folder)
        finally:
            build_osm_water_reach.OUT_PATH = live_out
            build_osm_water_reach.elevation_ft = live_elevation


def grade(records: list[dict], elevations: Path | None, previous: int | None, guard: bool) -> list[dict]:
    """apply_grade_gate() over the records, then write()'s guards and its `reachable` stamp. Raises SystemExit on a refusal."""
    with _grading(elevations) as folder:
        build_osm_water_reach.apply_grade_gate(records, quiet=True)
        build_osm_water_reach.write(records, guard=guard, previous=previous, path=folder / "verdicts.json")
    return records


def previous_reachable(path: Path | None) -> int | None:
    """build_osm_water_reach.read_previous_reachable_count(), on a named file."""
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("n_reachable")
    except json.JSONDecodeError:
        return None


def write_grade(con: duckdb.DuckDBPyConnection, records: list[dict], loaded_at: datetime) -> int:
    """Replace derived.osm_water_grade with one row per record. Returns the row count."""
    con.execute(f"create schema if not exists {SCHEMA}")
    con.execute(f"""
        create or replace table {SCHEMA}.{TABLE} (
            osm_id varchar,
            passes_grade boolean,
            drop_ft double,
            grade double,
            grade_floored boolean,
            reachable boolean,
            reason varchar,
            _loaded_at timestamptz
        )
    """)
    rows = [
        (
            record["osm_id"],
            record.get("passes_grade"),
            record.get("drop_ft"),
            record.get("grade"),
            record.get("grade_floored", False),
            record["reachable"],
            record.get("reason"),
            loaded_at,
        )
        for record in records
    ]
    if rows:
        con.executemany(f"insert into {SCHEMA}.{TABLE} values (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()[0]


def _landed(con: duckdb.DuckDBPyConnection) -> int:
    try:
        return con.execute(f"select count(*) from {POINTS}").fetchone()[0]
    except duckdb.CatalogException:
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--elevations", type=Path, help="EPQS answers keyed lat,lon at 6 dp, in place of the network")
    parser.add_argument(
        "--previous",
        type=Path,
        default=build_osm_water_reach.OUT_PATH,
        help="the last verdict file, for the drop guard (default: build_osm_water_reach.py's)",
    )
    args = parser.parse_args(argv)

    with duckdb.connect(str(args.warehouse)) as con:
        records = read_reach(con)
        guard = args.elevations is None and _landed(con) > 0
        try:
            grade(records, args.elevations, previous_reachable(args.previous) if guard else None, guard)
        except SystemExit as refusal:
            print(f"{SCHEMA}.{TABLE}: refusing to write: {refusal}")
            return 1
        finally:
            fetch_trail_water.flush_elevation_cache()
        written = write_grade(con, records, datetime.now(UTC))
    reachable = sum(1 for record in records if record["reachable"])
    print(f"{SCHEMA}.{TABLE}: {written:,} corridor OSM water points, {reachable:,} reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
