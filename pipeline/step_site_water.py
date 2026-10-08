"""step_site_water: which A.T. shelters and campsites have water a hiker can walk to, written to derived.site_water for dbt to read back.

    python step_site_water.py [--warehouse data/warehouse.duckdb] [--from-file <trail_water.json>]
    python step_site_water.py --derive [--previous <trail_water.json>]
    python step_site_water.py --candidates <json> --elevations <json>

pipeline/ELT.md's ledger rows PO07 and PO17, and "Python steps, outside dbt".
The rule is fetch_trail_water.py's, unchanged and called rather than copied:
for each shelter and campsite, the nearest point on a stream in each
hydrography (USGS's NHD flowlines and OSM's stream ways), the two merged where
they lie within SITE_WATER_MERGE_M (20 m) of each other, published only where
it is within MATCH_RADIUS_FT (100 ft) and no steeper than MAX_GRADE (15%)
over at least MIN_GRADE_RUN_FT (10 ft), measured from USGS EPQS elevations at
both ends; every refusal kept with its numbers. Each gate's evidence is on its
constant in fetch_trail_water.py, and that file stays the one home of all four.

WHY A STEP, AND WHY THE GATES STAY IN IT (decision 23 sends a rule to SQL
first). What is not arithmetic here cannot be SQL in this build: the
hydrography is 21 NHD GeoPackages of about 270 MB, downloaded and deleted in
turn, which stay files (decision 4), and fourteen Geofabrik state extracts
(#1652 — Download OSM's Geofabrik extracts at most once a month, into a
private raw bucket that outlives the 7-day Actions cache); and EPQS answers
one point at a time, at about 1.9 s a point, which is why it is asked only
about candidates inside the distance gate. So the gates sit between two reads
SQL cannot make, and moving the arithmetic would split this step in two around
a dbt invocation for rules that tests/test_fetch_trail_water.py already holds
(Reasoned). A later SQL attempt can take the nearest point, the merge and the
gates once the reaches near each site land as a table.

THE SITES ARE THE WAREHOUSE'S. fetch_trail_water.py fetches ATC's shelters and
campsites itself (build_water_distance.fetch_atc_features); here they are
int_points_of_interest__water_sites, the layers the extract already landed
(one extraction per upstream), in fetch_atc_features' order: shelters, then
campsites, each by name and then GlobalID. That order is the file's, and so
the order export_poi.py's load_trail_water() publishes the site water in.

THREE WAYS TO RUN, one rule:
- by default, land the last derivation as it is: `--from-file`, which is
  fetch_trail_water.OUT_PATH unless named, the file export_poi.py's
  load_trail_water() reads. That is what a publish does today unless
  somebody ticks publish-vector-data.yml's include_trail_water (default
  false; "~5.7 GB of USGS subregions / ~30 min"), and the file rides
  FETCH_OUTPUTS from the run that last derived it. No file is no site water,
  as it is for load_trail_water(). The monthly lane names the file
  refresh-reference.yml's pin job derived with fetch_trail_water.py
  --derive over the Geofabrik extracts the raw store keeps and pinned,
  which build-reference.yml's build reads back from the pin as
  data/raw/derived/trail_water.json, or the last landed one (#1652 —
  Download OSM's Geofabrik extracts at most once a month, into a private raw
  bucket that outlives the 7-day Actions cache; build_marts.py's lane_args);
- `--derive`: the hydrography and EPQS as fetch_trail_water.py reads them,
  with its two refusals: a dataset that loads no stream (EMPTY_READ) and a
  derivation that lost more than MAX_SITE_WATER_DROP_RATIO of the site water
  in `--previous`, the last derivation on disk. It writes the table, not the
  file: fetch_trail_water.py stays the writer of trail_water.json until the
  cutover (stage 4) decides who derives;
- `--candidates` and `--elevations` (build_marts.py --fixtures): each site's
  candidate reaches and the EPQS answers from files, never the network, so CI
  runs the gates on make_dbt_fixtures.py's rows. A point the elevations file
  does not hold has no elevation, which the grade gate reads as unknown and
  refuses, as it refuses a point EPQS will not answer. No drop guard: there
  is no last derivation of fixtures to hold them to.

The table is one row per site, in the file's order: the site, and either the
water it can reach or why it cannot, as the file's records carry them.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

import fetch_trail_water

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SITES = "intermediate.int_points_of_interest__water_sites"
SCHEMA = "derived"
TABLE = "site_water"
#: fetch_trail_water.py's two layers, in the order its _run() fetches them.
LAYERS = ("shelters", "campsites")


def read_sites(con: duckdb.DuckDBPyConnection, relation: str = SITES) -> dict[str, list[dict]]:
    """The shelters and campsites, by layer, as fetch_atc_features returns them: {global_id, name, lat, lon}, by name then id."""
    try:
        rows = con.execute(f"select layer, global_id, name, lat, lon from {relation}").fetchall()
    except duckdb.CatalogException as missing:
        raise SystemExit(
            f"{relation} is not in the warehouse: build it with dbt first (everything but "
            f"`source:derived+`), then run this step, then build `source:derived+`. ({missing})"
        ) from missing
    by_layer: dict[str, list[dict]] = {layer: [] for layer in LAYERS}
    for layer, global_id, name, lat, lon in rows:
        by_layer[layer].append({"global_id": global_id, "name": name, "lat": lat, "lon": lon})
    return {
        layer: sorted(features, key=lambda row: (row["name"] or "", row["global_id"])) for layer, features in by_layer.items()
    }


def offline_elevations(path: Path):
    """fetch_trail_water.elevation_ft's lookup against a file alone: a point it does not hold has no elevation."""
    answers = json.loads(path.read_text(encoding="utf-8"))

    def elevation_ft(lat: float, lon: float) -> float | None:
        return answers.get(f"{lat:.6f},{lon:.6f}")

    return elevation_ft


def derive(sites: dict[str, list[dict]], candidates_path: Path | None, elevations_path: Path | None) -> list[dict]:
    """fetch_trail_water.build() over these sites: its records, one per site, in order."""
    if candidates_path is not None:
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    else:
        candidates = fetch_trail_water.collect_streams([site for features in sites.values() for site in features])
    if elevations_path is None:
        return fetch_trail_water.build(sites, candidates)["sites"]
    live = fetch_trail_water.elevation_ft
    fetch_trail_water.elevation_ft = offline_elevations(elevations_path)
    try:
        return fetch_trail_water.build(sites, candidates)["sites"]
    finally:
        fetch_trail_water.elevation_ft = live


def drop_refusal(records: list[dict], previous: Path | None) -> str | None:
    """fetch_trail_water.py's write guard: why these records must not replace the last derivation, or None."""
    if previous is None:
        return None
    before = fetch_trail_water.existing_site_water_count(previous)
    now = sum(1 for record in records if record.get("water") is not None)
    if before and now < before * fetch_trail_water.MAX_SITE_WATER_DROP_RATIO:
        return (
            f"{now} sites with water against {before} in {previous} is past the "
            f"{fetch_trail_water.MAX_SITE_WATER_DROP_RATIO:.0%} drop guard"
        )
    return None


def _json(value) -> str | None:
    return None if value is None else json.dumps(value)


def write_site_water(con: duckdb.DuckDBPyConnection, records: list[dict], loaded_at: datetime) -> int:
    """Replace derived.site_water with one row per site record, in order. Returns the row count."""
    con.execute(f"create schema if not exists {SCHEMA}")
    con.execute(f"""
        create or replace table {SCHEMA}.{TABLE} (
            site_row integer,
            layer varchar,
            atc_global_id varchar,
            atc_name varchar,
            water json,
            unresolved varchar,
            candidate json,
            _loaded_at timestamptz
        )
    """)
    rows = [
        (
            row,
            record["layer"],
            record["atc_global_id"],
            record.get("atc_name"),
            _json(record.get("water")),
            record.get("unresolved"),
            _json(record.get("candidate")),
            loaded_at,
        )
        for row, record in enumerate(records)
    ]
    # No records is an empty table, not an error: executemany refuses an empty list.
    if rows:
        con.executemany(f"insert into {SCHEMA}.{TABLE} values (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument(
        "--from-file",
        type=Path,
        default=fetch_trail_water.OUT_PATH,
        help="the trail_water.json to land when not deriving (default: the one export_poi.py reads)",
    )
    parser.add_argument(
        "--derive", action="store_true", help="derive from the hydrography and EPQS, as fetch_trail_water.py does"
    )
    parser.add_argument(
        "--previous", type=Path, default=fetch_trail_water.OUT_PATH, help="the last derivation, for --derive's drop guard"
    )
    parser.add_argument("--candidates", type=Path, help="each site's candidate reaches, in place of the hydrography")
    parser.add_argument("--elevations", type=Path, help="EPQS answers keyed lat,lon at 6 dp, in place of the network")
    args = parser.parse_args(argv)
    if (args.candidates is None) != (args.elevations is None):
        parser.error("--candidates and --elevations go together: a derivation from files reads both")
    if args.derive and args.candidates is not None:
        parser.error("--derive reads the hydrography and EPQS; --candidates and --elevations replace them")

    with duckdb.connect(str(args.warehouse)) as con:
        if not args.derive and args.candidates is None:
            path = args.from_file
            records = json.loads(path.read_text(encoding="utf-8")).get("sites", []) if path.exists() else []
            origin = str(path) if path.exists() else f"{path}, which is absent"
        else:
            try:
                records = derive(read_sites(con), args.candidates, args.elevations)
            except ValueError as refusal:
                print(f"{SCHEMA}.{TABLE}: refusing to write: {refusal}.")
                return 1
            finally:
                fetch_trail_water.flush_elevation_cache()
            if refusal := drop_refusal(records, args.previous if args.derive else None):
                print(f"{SCHEMA}.{TABLE}: refusing to write: {refusal}.")
                return 1
            origin = "the hydrography and EPQS" if args.derive else "the fixtures' candidates"
        written = write_site_water(con, records, datetime.now(UTC))
    with_water = sum(1 for record in records if record.get("water") is not None)
    print(f"{SCHEMA}.{TABLE}: {written:,} sites, {with_water:,} with water a hiker can walk to, from {origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
