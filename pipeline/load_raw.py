"""Load already-fetched raw layers into the DuckDB warehouse - the L of ELT.

The dbt transform layer (pipeline/DBT.md, #100) works from tables, not from
files, and it works from RAW tables deliberately: the fetched GeoJSON lands
in a `raw` schema untouched, every column exactly as upstream sent it, so
every transform downstream is reproducible from a known starting point and
nothing gets silently reshaped on the way in. Extract stays where it is -
fetch_all.py / fetch_opentrail.py keep writing data/raw/*.geojson - and this
script is the bridge between them and dbt.

What loads is decided by a registry, not a glob: every ArcGIS feature layer
in sources.json - BOTH kinds of them - plus opentrail_at.geojson, whose
fetcher predates the registry. Table names are `raw_<provider>__<key>`
(raw_atc__shelters, raw_dec__dec_lean_tos, raw_opentrail__at), the naming
DBT.md's Phase D leans on: a second trail's sources become new rows here and
new staging models there, not a parallel pipeline.

BOTH KINDS, and until Phase D (#100) it was one. `lib/source_registry.py`
splits ArcGIS layers in two - the twelve A.T. layers `fetch_all.py` pulls
(no `kind` at all, the registry's default) and the `external_arcgis_layer`
entries `fetch_external_layers.py` pulls into `data/raw/external/` - and
this loader's filter used to be `kind is None`, which is the A.T. set and
only the A.T. set. That was correct when it was written and had quietly
become the thing #100 exists to prevent: the four other organizations'
trail lines were being fetched and exported - 21,805 features in
nearby_trails.geojson, 7.3 MB gzipped, measured on a live fetch 2026-08-25
(pipeline/README.md) - while the warehouse could not see one row of any of
them. `lib/source_registry.py`'s own
comment on EXTERNAL_ARCGIS_LAYER anticipated this exactly - "load_raw.py's
kind filter keeps them out of the warehouse the same way, until #100's
staging models take them deliberately" - and this is that deliberate take.

The two fetchers write to different directories and that difference is
carried here rather than flattened: an A.T. layer is `<key>.geojson` under
`data/raw/`, an external one is `external/<key>.geojson`, which is
fetch_external_layers.py's own on-disk boundary and not this script's to
move.

Everything else in sources.json is some other shape - club PDFs, published
notice pages, a watched-only registration, a Geofabrik extract, a weekly
national polygon file - with no per-feature GeoJSON at these paths, and
stays out. DBT.md's Phase D section says which and why for each.

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
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from lib.source_registry import arcgis_sources, external_arcgis_sources, load_registry

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
SOURCES_PATH = ROOT / "sources.json"

# fetch_external_layers.py's own output directory, relative to RAW_DIR. Named
# here rather than imported so this script does not depend on a fetcher it
# never calls; tests/test_load_raw.py holds the two spellings together.
EXTERNAL_SUBDIR = "external"

# fetch_opentrail.py predates sources.json (its upstream is a community API,
# not an ArcGIS layer) and writes opentrail_at.geojson without a registry
# row. Registered here by hand so the warehouse's contents are still decided
# in exactly one place - this constant plus the registry, nothing globbed.
EXTRA_LAYERS = [("opentrail", "at", "opentrail_at.geojson")]


#: What a multi-word `provider` is called in a table name.
#:
#: WHY THIS IS A TABLE AND NOT A RULE. This function used to be "take the
#: first word, lowercase it", which is right for every provider that was
#: registered when it was written - ATC, and nothing else. Two of the
#: providers Phase D loads are `NYS OPRHP` and `NYS DEC`, and that rule
#: collapses BOTH to `nys`: not a name collision (the key disambiguates the
#: table) but a table named after the state where it claims to be named after
#: the organization, on the layer that decides whether a hiker sees a lean-to
#: or a state-park bathroom. Measured against the live registry 2026-08-27:
#: 33 entries, 9 distinct providers, and exactly one first-word collision -
#: `NYS`, shared by `NYS OPRHP` and `NYS DEC` across 12 of the 33 entries.
#:
#: Spelled out rather than derived, following lib/source_registry.py's
#: POI_SOURCE_KEYS and the reason it gives for itself: a layer that turns out
#: to differ should differ in a table, not somewhere clever. `Mohonk
#: Preserve` is here for readability rather than to fix a collision -
#: `mohonk` is what sources.json's own keys call it.
PROVIDER_SLUGS = {
    "NYS OPRHP": "oprhp",
    "NYS DEC": "dec",
    "Mohonk Preserve": "mohonk",
}


def _provider_slug(provider: str) -> str:
    """'ATC' -> 'atc': the lowercase token table and staging names build on.

    A one-word provider is its own slug, lowercased. A multi-word one must
    be in PROVIDER_SLUGS, and RAISES if it is not - loudly, at load time,
    naming the provider and this constant. Falling back to the first word is
    what produced the `NYS` collision described above, and a wrong table name
    is not the kind of thing anybody re-reads once the build is green."""
    if provider in PROVIDER_SLUGS:
        return PROVIDER_SLUGS[provider]
    if len(provider.split()) == 1:
        return provider.lower().replace("-", "_")
    raise ValueError(
        f"No table-name slug for provider {provider!r}. A multi-word provider needs a row in "
        "load_raw.PROVIDER_SLUGS - guessing from the first word is what named two different New "
        "York State agencies `nys`."
    )


def registered_layers() -> list[tuple[str, str, str]]:
    """(provider_slug, key, path_relative_to_raw_dir) for every loadable source.

    Both ArcGIS kinds, asked of lib/source_registry.py rather than by
    reading `kind` here - the same split fetch_all.py and
    fetch_external_layers.py use, so a fourth kind arriving cannot mean
    three different things in three files. Everything else in sources.json
    is another shape entirely and has no per-feature GeoJSON to load."""
    registry = load_registry(SOURCES_PATH)
    layers = [(_provider_slug(entry["provider"]), entry["key"], f"{entry['key']}.geojson") for entry in arcgis_sources(registry)]
    layers += [
        (_provider_slug(entry["provider"]), entry["key"], f"{EXTERNAL_SUBDIR}/{entry['key']}.geojson")
        for entry in external_arcgis_sources(registry)
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
