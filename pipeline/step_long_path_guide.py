"""step_long_path_guide: NYNJTC's Long Path guide placed as waypoints, written to derived.long_path_guide for dbt to read back.

    python step_long_path_guide.py [--warehouse data/warehouse.duckdb]

pipeline/ELT.md's ledger row PO36, and "Python steps, outside dbt".

The rule is lib/nynjtc_long_path_guide.py's build_records(), called rather
than copied: each section's mile-marked entries classified by type (the
narrow water rule, the lean-to that is not a picnic shelter, the camping
area that is no pin), placed where NYNJTC's own coordinates put them
(`stated`, high confidence) or by walking the guide's mile along that
section's line of the Long Path layer (`interpolated`, low confidence, with
INTERPOLATION_ERROR_M, the measured p90 of 500 m, carried on the record), and
de-duplicated where the guide names one place twice (STATED_DUPLICATE_M,
100 m, for two lots with coordinates). Every entry it does not place is
counted by reason, and the step prints the count.

WHY A STEP (decision 23 sends a rule to SQL first). The classification is
some thirty regular expressions with look-ahead and look-behind, which RE2,
DuckDB's engine, does not have, so the patterns themselves would have to be
rewritten, and each rewrite is a new judgement about what a sentence means on
the water path (Reasoned). The ledger already files the guide's reading as
extraction ("a guide parse is extraction"); the placement around it is
lib/nynjtc_long_path_guide.py's and its 42 tests hold it.

THE INPUTS ARE THE WAREHOUSE'S: the sections the guide_pages kind landed
(stg_nynjtc__long_path_guide, in section order, as the extract's parse wrote
them) and the Long Path layer's lines (stg_nynjtc__long_path, in the raw
table's order, which section_lines() chains). Whether the records may reach
a hiker is not decided here: the registry's reaches_hikers is, through
int_sources__publication, as export_nearby_poi.py's guide_records() asks it.
It reads the two staging models rather than an intermediate, and so has no
exposure: the project evaluator holds an exposure's parents to tables, and a
pass-through table of staged rows would add a model and nothing else.

One row per record, in build_records()' order, with the record whole.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from lib import nynjtc_long_path_guide as guide

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SECTIONS = "staging.stg_nynjtc__long_path_guide"
LINES = "staging.stg_nynjtc__long_path"
SCHEMA = "derived"
TABLE = "long_path_guide"
#: The record fields the table carries as columns, in _record()'s order.
COLUMNS = (
    ("id", "varchar"),
    ("poi_type", "varchar"),
    ("trail_id", "varchar"),
    ("source", "varchar"),
    ("source_feature_id", "varchar"),
    ("name", "varchar"),
    ("lat", "double"),
    ("lon", "double"),
    ("confidence", "varchar"),
    ("description", "varchar"),
    ("lp_section", "integer"),
    ("section_mile", "double"),
    ("placement", "varchar"),
    ("source_url", "varchar"),
    ("position_error_m", "integer"),
    ("off_trail_miles", "double"),
    ("water_reliability", "varchar"),
)


def read_sections(con: duckdb.DuckDBPyConnection, relation: str = SECTIONS) -> list[guide.Section]:
    """The landed sections as Section objects, in section order."""
    rows = con.execute(
        f"select section_number, title, distance_miles, parks, url, parking, camping, entries, notes "
        f"from {relation} order by section_number"
    ).fetchall()
    return [
        guide.Section.from_dict(
            {
                "number": number,
                "title": title,
                "distance_miles": distance,
                "parks": parks,
                "url": url,
                "parking": json.loads(parking) if parking else [],
                "camping": json.loads(camping) if camping else [],
                "description": json.loads(entries) if entries else [],
                "notes": json.loads(notes) if notes else {},
            }
        )
        for number, title, distance, parks, url, parking, camping, entries, notes in rows
    ]


def read_lines(con: duckdb.DuckDBPyConnection, relation: str = LINES) -> list[dict]:
    """The Long Path layer's features as section_lines() reads them: LP_Section and the GeoJSON geometry, in file order."""
    rows = con.execute(
        f"select lp_section, st_asgeojson(geom) from {relation} where geom is not null order by source_row"
    ).fetchall()
    return [
        {"type": "Feature", "properties": {"LP_Section": section}, "geometry": json.loads(geometry)} for section, geometry in rows
    ]


def write_guide(con: duckdb.DuckDBPyConnection, records: list[dict], loaded_at: datetime) -> int:
    """Replace derived.long_path_guide with one row per record. Returns the row count."""
    con.execute(f"create schema if not exists {SCHEMA}")
    columns = ", ".join(f"{name} {kind}" for name, kind in COLUMNS)
    con.execute(f"create or replace table {SCHEMA}.{TABLE} (record_row integer, {columns}, record json, _loaded_at timestamptz)")
    rows = [
        (row, *(record.get(name) for name, _ in COLUMNS), json.dumps(record), loaded_at) for row, record in enumerate(records)
    ]
    if rows:
        marks = ", ".join("?" * (len(COLUMNS) + 3))
        con.executemany(f"insert into {SCHEMA}.{TABLE} values ({marks})", rows)
    return con.execute(f"select count(*) from {SCHEMA}.{TABLE}").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    args = parser.parse_args(argv)

    with duckdb.connect(str(args.warehouse)) as con:
        con.execute("load spatial")
        try:
            sections = read_sections(con)
            lines = read_lines(con)
        except duckdb.CatalogException as missing:
            raise SystemExit(
                f"{SECTIONS} or {LINES} is not in the warehouse: build it with dbt first (everything but "
                f"`source:derived+`), then run this step. ({missing})"
            ) from missing
        records, stats = guide.build_records(sections, lines)
        written = write_guide(con, records, datetime.now(UTC))
    print(
        f"{SCHEMA}.{TABLE}: {written:,} waypoints from {stats['sections']} section pages "
        f"({stats['sections_with_a_line']} with a line), {stats['entries_placed']['stated']:,} at NYNJTC's own "
        f"coordinates, {stats['entries_placed']['interpolated']:,} placed by mile, {stats['duplicates_merged']:,} repeats merged"
    )
    for reason, count in stats["skipped"].items():
        print(f"  skipped {count:>5,}  {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
