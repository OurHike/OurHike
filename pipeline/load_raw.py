"""Load already-fetched raw layers into the DuckDB warehouse - the L of ELT.

The dbt transform layer (pipeline/DBT.md, #100) works from tables, not from
files, and it works from RAW tables deliberately: the fetched GeoJSON lands
in a `raw` schema untouched, every column exactly as upstream sent it, so
every transform downstream is reproducible from a known starting point and
nothing gets silently reshaped on the way in. Extract stays where it is -
fetch_all.py / fetch_opentrail.py keep writing data/raw/*.geojson - and this
script is the bridge between them and dbt.

What loads is decided by a registry, not a glob: every ArcGIS feature layer
in sources.json (the entries lib/source_registry.py reads; hand-registered
`kind` entries are other shapes - PDFs, notice pages, watched-only rows -
and stay out of the warehouse), plus opentrail_at.geojson, whose fetcher
predates the registry. Table names are `raw_<provider>__<key>`
(raw_atc__shelters, raw_opentrail__at), the naming DBT.md's Phase D leans
on: a second trail's sources become new rows here and new staging models
there, not a parallel pipeline.

Two bookkeeping columns ride along on every table, underscore-prefixed so
they cannot collide with an upstream field: `_loaded_at` (when this load
ran) and `_source_path` (the file it came from). DBT.md is upfront that
`_loaded_at` measures "when did load_raw.py last run", NOT upstream
freshness - real upstream change-detection lives in the fetchers
(dataLastEditDate, ETags) and this is a narrower, complementary signal.

A registered layer whose file is missing is reported and skipped rather
than failing the run: the loader's contract is "everything fetched is
loaded", not "everything registered is fetched" - fetch completeness is
fetch_all.py's job, and a partial local fetch (one layer for a spike) would
otherwise make the warehouse unbuildable. The report says what was skipped
so the gap is visible, not silent.

Raster pixel data stays out of the warehouse entirely - see DBT.md's
"Deliberately excluded" paragraph.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SOURCES_PATH = ROOT / "sources.json"

# fetch_opentrail.py predates sources.json (its upstream is a community API,
# not an ArcGIS layer) and writes opentrail_at.geojson without a registry
# row. Registered here by hand so the warehouse's contents are still decided
# in exactly one place - this constant plus the registry, nothing globbed.
EXTRA_LAYERS = [("opentrail", "at", "opentrail_at.geojson")]


def _provider_slug(provider: str) -> str:
    """'ATC' -> 'atc': the lowercase token table and staging names build on.

    Only the first word, lowercased - 'OpenStreetMap contributors' would be
    'openstreetmap' - so the slug stays a valid SQL identifier fragment
    without a second naming convention to remember."""
    return provider.split()[0].lower().replace("-", "_")


def registered_layers() -> list[tuple[str, str, str]]:
    """(provider_slug, key, filename) for every source this script loads.

    ArcGIS feature layers only, from sources.json: an entry carrying a
    `kind` is some other shape (club PDFs, published notice pages,
    watched-only registrations) with no per-feature GeoJSON to load."""
    sources = json.loads(SOURCES_PATH.read_text())["sources"]
    layers = [
        (_provider_slug(entry["provider"]), entry["key"], f"{entry['key']}.geojson")
        for entry in sources
        if entry.get("kind") is None
    ]
    return layers + EXTRA_LAYERS


def load_raw(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> tuple[list[str], list[str]]:
    """Load every registered layer whose file exists into the `raw` schema.

    Returns (loaded_table_names, skipped_filenames). CREATE OR REPLACE per
    table: a re-run replaces wholesale rather than appending, so the
    warehouse always mirrors the newest fetch and never accumulates stale
    rows from an older one."""
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    # Naive UTC rather than TIMESTAMPTZ, deliberately: DuckDB's Python
    # client needs pytz to hand a TIMESTAMPTZ value back to Python, and the
    # pytest CI job does not carry that dependency - bitten there
    # 2026-08-18. The column is always UTC; it just does not say so in its
    # type.
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)

    loaded: list[str] = []
    skipped: list[str] = []
    for provider, key, filename in registered_layers():
        path = raw_dir / filename
        if not path.exists():
            skipped.append(filename)
            continue
        table = f"raw_{provider}__{key}"
        con.execute(
            f"""
            CREATE OR REPLACE TABLE raw.{table} AS
            SELECT *, ?::TIMESTAMP AS _loaded_at, ? AS _source_path
            FROM ST_Read(?)
            """,
            [loaded_at, str(path), path.as_posix()],
        )
        loaded.append(table)
    return loaded, skipped


def main(warehouse_path: Path = WAREHOUSE_PATH, raw_dir: Path = RAW_DIR) -> dict:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse_path))
    try:
        loaded, skipped = load_raw(con, raw_dir)
        counts = {
            table: con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]  # noqa: S608 - table names come from the registry above, not input
            for table in loaded
        }
    finally:
        con.close()

    print(f"Warehouse -> {warehouse_path}")
    for table, count in counts.items():
        print(f"  raw.{table}: {count} rows")
    if skipped:
        print(f"  Skipped (registered, not fetched here): {', '.join(sorted(skipped))}")
    return {"loaded": counts, "skipped": sorted(skipped)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    main(args.warehouse, args.raw_dir)
