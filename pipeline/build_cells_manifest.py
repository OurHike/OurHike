"""Build cells.json - the corridor cell grid plus each cell's quad list,
consumed by fetch_and_mosaic_cell.py (and, in CI, by the matrix job that
fans out one job per cell). Cheap: DuckDB queries over the small corridor
polygon and USGS metadata CSV, no rasters touched.

Corridor: built fresh via lib/corridor.py's build_corridor() (shared with
export_poi.py/export_trails.py - see that module's docstring) from
data/raw/centerline.geojson, then exported to CORRIDOR_PATH as this script's
own artifact - never read from data/spike/corridor.geojson, which is stale
proof-of-concept output from spike_corridor.py (see lib/corridor.py's
docstring for why that file must never be read as if it were current).
fetch_and_mosaic_cell.py reads this same CORRIDOR_PATH by default, so the
cell grid computed here and the corridor its per-cell mosaic clips against
can never silently diverge onto two different polygons.

Completeness: unlike spike_raster_mosaic.py's "every corridor-intersecting
cell must produce a tile" hard-fail, cells.json itself had no equivalent
check anywhere - a cell silently dropped from the grid, or left with an
incomplete/empty quad list, would go completely undetected by anything
downstream. So this checks its own output before writing it: the cells list
must be non-empty, and every cell must have at least one assigned quad. A
zero-quad cell is a hard failure here, not just a warning - verified against
the real 51-cell AT corridor manifest, where the smallest actual cell still
has 2 quads, so an empty list is never a legitimate edge-of-corridor result,
only a sign this script's own query went wrong.

    .venv/Scripts/python build_cells_manifest.py
"""

import json
import sys
from pathlib import Path

import duckdb

from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import build_corridor
from lib.corridor_grid import build_cells_manifest

ROOT = Path(__file__).parent
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
CORRIDOR_PATH = ROOT / "data" / "raw" / "corridor.geojson"
METADATA_CSV_PATH = ROOT / "data" / "raw" / "topo_metadata" / "ustopo_current.csv"
OUT_PATH = ROOT / "data" / "raw" / "cells.json"


def write_corridor_geojson(con: duckdb.DuckDBPyConnection, out_path: Path) -> None:
    """Export the 'corridor' table build_corridor() just built on `con` to
    `out_path` as GeoJSON - the same COPY TO ... FORMAT GDAL idiom
    export_poi.py/export_trails.py already use for their own output. Writing
    it out (rather than keeping the corridor purely in-memory) is what lets
    lib/corridor_grid.py's file-based compute_cells()/load_quad_bounds() -
    and fetch_and_mosaic_cell.py's load_corridor_geom() - consume a fresh
    corridor without needing to know about the DuckDB connection that built
    it."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # COPY TO refuses to overwrite an existing file, and this needs to be
    # safely re-runnable.
    out_path.unlink(missing_ok=True)
    con.execute(f"COPY corridor TO '{out_path.as_posix()}' WITH (FORMAT GDAL, DRIVER 'GeoJSON')")


def check_manifest_is_complete(manifest: dict) -> None:
    """Fail loudly (print + sys.exit(1)) if this script's own output is
    incomplete: the cells list itself is empty, or any individual cell's
    quad list is empty - see the module docstring for why zero quads is
    treated as a hard failure rather than just a warning. A no-op for a
    healthy manifest, so main() can call this unconditionally."""
    cells = manifest["cells"]
    counts = {"cells": len(cells)}
    counts.update({f"cell {cell['index']} quads": len(cell["quads"]) for cell in cells})
    fail_if_incomplete(count_problems(counts), label="Incomplete cells manifest")


def main() -> int:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    print("Building 30-mile corridor from centerline...")
    build_corridor(con, CENTERLINE_PATH)
    write_corridor_geojson(con, CORRIDOR_PATH)
    print(f"  -> {CORRIDOR_PATH}")

    manifest = build_cells_manifest(CORRIDOR_PATH, METADATA_CSV_PATH)
    check_manifest_is_complete(manifest)

    OUT_PATH.write_text(json.dumps(manifest, indent=2))
    cells = manifest["cells"]
    total_quad_refs = sum(len(c["quads"]) for c in cells)
    print(f"{len(cells)} cells, {total_quad_refs} total (cell, quad) assignments -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
