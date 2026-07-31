"""Fetch + mosaic exactly one corridor cell - the per-cell unit of work a
GitHub Actions matrix job runs, so the whole-corridor raster pipeline can
run on hosted runners whose disk can't hold the full ~14GB of raw quads plus
~3.7GB of mosaicked output at once (see TECHNICAL_ARCHITECTURE.md/the CI
plan for the numbers). Peak disk for a single cell is at most a few hundred
MB (worst measured case: 81 quads, ~689MB raw), comfortably under that.

That 3.7GB is post-compression. Before mosaic_one_cell() started writing
DEFLATE, the set was 14.59GB and this docstring claimed 9.5GB - `du -sh`'s
allocated-block figure on the dev machine, not what a Linux runner would
actually need. Anyone sizing a runner from the old number was ~4x low.

Deliberately a new script rather than a --cell-index flag bolted onto
fetch_topo_quads.py/spike_raster_mosaic.py: those two stay documented and
behaving as whole-corridor tools for local use (see pipeline/README.md);
this one composes their already-extracted building blocks
(fetch_quads_for_cell, resolve_state_index, index_quads_in_dir,
mosaic_one_cell) for the per-cell case, plus fix_corrupted_quads.py's
fix_quad() for reactive corruption recovery.

Fetches into a scratch directory distinct from fetch_topo_quads.py's
data/raw/topo_quads/<state>/ (data/raw/topo_quads_cell_NNN/ instead), so a
local whole-corridor run and a local per-cell run can never collide over the
same files.

Requires cells.json and the corridor polygon (both build_cells_manifest.py -
the corridor is built fresh there via lib/corridor.py, not read from the
stale data/spike/corridor.geojson - see that script's docstring) and the
USGS metadata CSV (fetch_topo_quads.fetch_metadata_csv()) to already exist -
all three are small/fast and are built once per run by CI's `compute-cells`
job, not per cell. DEFAULT_CORRIDOR_PATH must keep pointing at the same path
build_cells_manifest.py writes CORRIDOR_PATH to, or this script's per-cell
mosaic would silently clip against a different corridor than the one that
computed the cell grid it's fetching for.

Completeness: a cell where some but not all of its assigned quads make it
into the final mosaic (corrupted-and-unfixable, or unmatched against the S3
listing) fails run_cell() loudly (RuntimeError) rather than only printing a
warning - in the CI matrix model this runs as one of ~51 unattended parallel
jobs, so a print nobody is watching isn't a real signal that a cell shipped
with a coverage hole.

    .venv/Scripts/python fetch_and_mosaic_cell.py --cell-index 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import rasterio

from fetch_topo_quads import fetch_quads_for_cell, resolve_state_index
from fix_corrupted_quads import fix_quad
from lib.corridor_grid import load_corridor_geom
from spike_raster_mosaic import index_quads_in_dir, load_neatlines, mosaic_one_cell

ROOT = Path(__file__).parent
DEFAULT_CELLS_JSON = ROOT / "data" / "raw" / "cells.json"
DEFAULT_METADATA_CSV = ROOT / "data" / "raw" / "topo_metadata" / "ustopo_current.csv"
DEFAULT_CORRIDOR_PATH = ROOT / "data" / "raw" / "corridor.geojson"
DEFAULT_OUT_DIR = ROOT / "data" / "processed" / "topo_background"


def load_cell(cells_json: Path, cell_index: int) -> dict:
    cells = json.loads(cells_json.read_text())["cells"]
    cell = next((c for c in cells if c["index"] == cell_index), None)
    if cell is None:
        raise ValueError(f"cell {cell_index} not found in {cells_json}")
    return cell


def run_cell(
    cell_index: int, cells_json: Path, metadata_csv: Path, corridor_path: Path, out_dir: Path, scratch_dir: Path
) -> Path:
    cell = load_cell(cells_json, cell_index)
    product_filenames = cell["quads"]

    quads_dir = scratch_dir / "quads"
    fallback_dir = scratch_dir / "fallback"
    quads_dir.mkdir(parents=True, exist_ok=True)
    fallback_dir.mkdir(parents=True, exist_ok=True)

    states = sorted({pf.split("_", 1)[0] for pf in product_filenames})
    print(f"cell {cell_index}: {len(product_filenames)} quads across {len(states)} state(s): {states}")
    state_index = resolve_state_index(states)

    manifest: dict = {}  # ephemeral - a fresh scratch dir has nothing to skip against
    results = fetch_quads_for_cell(product_filenames, state_index, quads_dir, manifest)

    for product_filename, result in zip(product_filenames, results):
        if result["status"] == "corrupted":
            print(f"  {product_filename}: corrupted after download, attempting inline fix...")
            fix_result = fix_quad(product_filename, result["path"], metadata_csv, fallback_dir)
            if fix_result["status"] == "failed":
                print(f"  {product_filename}: fix failed - this quad's coverage will be missing from the cell")
        elif result["status"] == "unmatched":
            print(f"  {product_filename}: UNMATCHED ({result.get('reason')})")

    neatlines = load_neatlines(metadata_csv)
    quad_index = index_quads_in_dir(quads_dir, fallback_dir, neatlines)
    matching = [(path, neatline) for path, _bounds, neatline in quad_index]

    # A cell where SOME but not all assigned quads make it through (corrupted-
    # and-unfixable, or unmatched against the S3 listing) must fail just as
    # loudly as the zero-matches case below - until now this only ever
    # printed a warning (see the "fix failed"/"UNMATCHED" prints above) and
    # silently shipped a tile with a coverage hole. In the CI matrix model
    # this is one of ~51 unattended parallel jobs, so this exception is the
    # only signal anyone gets; the per-quad prints above still explain why.
    if len(matching) < len(product_filenames):
        missing = len(product_filenames) - len(matching)
        raise RuntimeError(
            f"cell {cell_index}: {missing}/{len(product_filenames)} assigned quads did not make it into the "
            "mosaic (see per-quad warnings above) - refusing to ship a cell with a silent coverage hole"
        )

    corridor_geom = load_corridor_geom(corridor_path)
    arr, result = mosaic_one_cell(tuple(cell["bbox"]), matching, corridor_geom)
    if arr is None:
        raise RuntimeError(f"cell {cell_index} produced no tile: {result['print_reason']}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tile_{cell_index:03d}.tif"
    with rasterio.open(out_path, "w", **result) as dst:
        dst.write(arr)
    print(f"cell {cell_index}: {len(matching)} quads -> {out_path.name} ({out_path.stat().st_size / 1e6:.1f} MB)")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-index", type=int, required=True)
    parser.add_argument("--cells-json", type=Path, default=DEFAULT_CELLS_JSON)
    parser.add_argument("--metadata-csv", type=Path, default=DEFAULT_METADATA_CSV)
    parser.add_argument("--corridor", type=Path, default=DEFAULT_CORRIDOR_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    scratch_dir = ROOT / "data" / "raw" / f"topo_quads_cell_{args.cell_index:03d}"
    run_cell(args.cell_index, args.cells_json, args.metadata_csv, args.corridor, args.out_dir, scratch_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
