"""step_weather_squares: the NBM weather squares build_weather_squares.py chose, into derived.weather_squares for dbt to read.

    python step_weather_squares.py [--warehouse data/warehouse.duckdb] [--squares data/raw/weather/squares.json]

WN03 of pipeline/ELT.md's ledger moves the placement of NWS alerts on those
squares to SQL (int_warnings__nws_alert_shapes, int_warnings__nws_placed).
The squares themselves stay build_weather_squares.py's, a Python job outside
dbt: which squares lie under a trail or a waypoint is read from the release's
published files on NOAA's grid, a square's water test reads two NOAA rasters
(URMA's terrain, HRRR's land mask), which no table here may hold (decision 35,
"No raster lands as data"), and its NWS zones come from NWS's zone shapefiles.
That job writes squares.json, and export_weather_alerts.py reads it today.

THIS STEP IS THE HAND-OFF, and does nothing else. It lands the file's document
whole, as one row, so the SQL reads exactly what export_weather_alerts.py
reads, and it refuses the file that script refuses: one from before each
square's zones were listed ("run build_weather_squares.py first"). It reads no
intermediate, so build_marts.py could run it at any point; it is a step, and
not an extract resource, because the squares are this project's own answer,
built per release by the weather job, not anybody's upstream data.

WHAT THE TARGET CHANGES, and this does not: ELT.md's hourly conditions build
reads the weather squares deferred from the monthly build ("Running it"), so
the monthly build has to hold them, and squares.json is today a file the
weather job (publish-weather.yml) caches per release. Whether this step reads
that cache, or build_weather_squares.py's rules move into the build
themselves, is stage 4's. Until then a build without the file stops here.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent
WAREHOUSE_PATH = ROOT / "data" / "warehouse.duckdb"
# build_weather_squares.py's SQUARES_PATH, which export_weather_alerts.py reads too. Written out
# rather than imported: that module imports rasterio and numpy for the half of its job this step
# does not do.
SQUARES_PATH = ROOT / "data" / "raw" / "weather" / "squares.json"
SCHEMA = "derived"
TABLE = "weather_squares"


def read_squares(path: Path) -> dict:
    """squares.json's document, refused as export_weather_alerts.py's main() refuses it."""
    try:
        document = json.loads(path.read_text())
    except OSError as missing:
        raise SystemExit(
            f"{path} is not there: build_weather_squares.py writes it, for the release this build reads"
        ) from missing
    if "zones" not in document:
        raise SystemExit(f"{path} predates each square's zones; run build_weather_squares.py first")
    return document


def write_weather_squares(con: duckdb.DuckDBPyConnection, document: dict, loaded_at: datetime) -> int:
    """Replace derived.weather_squares with the document's one row. Returns the number of trail squares it lists."""
    con.execute(f"create schema if not exists {SCHEMA}")
    con.execute(
        f"""
        create or replace table {SCHEMA}.{TABLE} as
        select
            cast(? as varchar) as release,
            cast(? as varchar) as document_json,
            cast(? as timestamptz) as _loaded_at
        """,
        [document.get("release"), json.dumps(document, separators=(",", ":")), loaded_at.isoformat()],
    )
    return len({tuple(square) for squares in document.get("cells", {}).values() for square in squares})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--squares", type=Path, default=SQUARES_PATH, help="build_weather_squares.py's squares.json")
    args = parser.parse_args(argv)
    document = read_squares(args.squares)
    with duckdb.connect(str(args.warehouse)) as con:
        squares = write_weather_squares(con, document, datetime.now(UTC))
    print(f"{SCHEMA}.{TABLE}: release {document.get('release')}, {squares:,} trail squares, from {args.squares}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
