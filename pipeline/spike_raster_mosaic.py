"""Mosaic + clip the real bulk USGS topo quads (see fetch_topo_quads.py) into
the actual corridor-clipped background raster - the real-scale follow-up to
spike_raster_clip.py's single-tile prototype.

Real complications the single-tile prototype didn't have to deal with:
- Each quad is in its own native UTM zone CRS (they vary by longitude), so
  they can't be merged directly - each is lazily reprojected to EPSG:4326
  via a WarpedVRT before merging.
- 1,654 quads at native ~2m/pixel resolution is far more data than needed
  for a phone background map, and a single mosaic sized to the corridor's
  full bounding rectangle (GA to Maine) would be enormous even downsampled,
  since the actual corridor is a thin ~60-mile-wide winding band, not a
  filled rectangle. So this processes in small geographic cells (matching
  the corridor-intersecting grid used elsewhere in the pipeline) and
  outputs one clipped tile per cell, skipping cells with no corridor
  overlap - the same reason real map tile systems don't ship one giant image.
- Every US Topo GeoTIFF is a scan of the *entire printed map sheet* - a white
  margin plus a header/footer collar (USGS/US Topo logos, title, scale bar,
  legend, adjoining-quadrangle diagram) - and its georeferenced raster extent
  covers that whole sheet, not just the actual mapped area. Left uncropped,
  that collar gets treated as real terrain and shows up as white bands and
  text in the exported background. USGS's own metadata CSV
  (ustopo_current.csv, already fetched by fetch_topo_quads.py) gives the true
  neatline per quad via westbc/eastbc/northbc/southbc - a clean 7.5'x7.5' box
  for a standard quad, confirmed noticeably smaller than the raw raster's
  full extent (e.g. CT_Ansonia: 0.125x0.125deg neatline vs a ~0.17x0.16deg
  raster). Each quad is cropped to that neatline before reprojecting.
"""

import csv
import json
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from fetch_topo_quads import bare_key
from lib.completeness import fail_if_incomplete
from lib.corridor import build_corridor
from lib.corridor_grid import compute_cells

CENTERLINE_PATH = Path(__file__).parent / "data" / "raw" / "centerline.geojson"
QUADS_DIR = Path(__file__).parent / "data" / "raw" / "topo_quads"
FALLBACK_DIR = Path(__file__).parent / "data" / "raw" / "topo_quads_fallback"
OUT_DIR = Path(__file__).parent / "data" / "processed" / "topo_background"
METADATA_CSV_PATH = Path(__file__).parent / "data" / "raw" / "topo_metadata" / "ustopo_current.csv"

TARGET_RES_DEG = 0.0001  # ~11m/pixel at these latitudes - plenty for a phone background map
DST_CRS = "EPSG:4326"


def load_neatlines(metadata_csv_path: Path | None = None):
    """Maps each quad's bare key (see fetch_topo_quads.bare_key) to its real
    neatline bounds (west, south, east, north) from USGS's own metadata CSV -
    the true mapped area, not the collar-inflated raster extent.

    `metadata_csv_path` defaults via a None sentinel, resolved inside the
    body, rather than `= METADATA_CSV_PATH` directly in the signature - a
    signature default is bound once at import time, so
    monkeypatch.setattr(module, "METADATA_CSV_PATH", ...) in a test would
    silently stop taking effect on this parameter (a real bug caught while
    writing this refactor - see test_load_neatlines_matches_dated_filenames_
    via_bare_key, which relies on exactly that monkeypatch working)."""
    if metadata_csv_path is None:
        metadata_csv_path = METADATA_CSV_PATH
    neatlines = {}
    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = bare_key(row["product_filename"].rsplit(".", 1)[0])
            neatlines[key] = (float(row["westbc"]), float(row["southbc"]), float(row["eastbc"]), float(row["northbc"]))
    return neatlines


def open_cropped_vrt(path, neatline):
    """Open `path` reprojected to DST_CRS via a WarpedVRT, cropped to
    `neatline` (west, south, east, north) instead of auto-sizing from the
    full source extent - excludes the collar for any quad with a metadata
    match. Falls back to the old auto-sized behavior if neatline is None
    (shouldn't normally happen for a real USGS quad, but not fatal if it
    does - better a slightly-oversized tile than a crashed run)."""
    src = rasterio.open(path)
    if neatline is None:
        return WarpedVRT(src, crs=DST_CRS, resolution=(TARGET_RES_DEG, TARGET_RES_DEG))
    west, south, east, north = neatline
    width = max(1, round((east - west) / TARGET_RES_DEG))
    height = max(1, round((north - south) / TARGET_RES_DEG))
    dst_transform = transform_from_bounds(west, south, east, north, width, height)
    return WarpedVRT(src, crs=DST_CRS, transform=dst_transform, width=width, height=height)


def load_corridor_and_cells():
    """Builds the 30-mile AT corridor fresh from CENTERLINE_PATH on every
    call, via lib/corridor.py's build_corridor() - never by reading
    data/spike/corridor.geojson, which is stale proof-of-concept output that
    predates the last real centerline refetch (see lib/corridor.py's module
    docstring for the dates involved).

    compute_cells() (lib/corridor_grid.py, shared with
    fetch_and_mosaic_cell.py's per-cell path, so the two can't silently
    compute different grids) only knows how to read a corridor from a file
    path, not an in-memory table, so the freshly-built corridor is written
    to a temp GeoJSON file that compute_cells() reads - the same fresh build
    the returned geometry itself comes from, not a second, independently
    stale-able source."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    build_corridor(con, CENTERLINE_PATH)
    corridor_geom = json.loads(con.execute("SELECT ST_AsGeoJSON(geom) FROM corridor").fetchone()[0])

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_corridor_path = Path(tmp_dir) / "corridor.geojson"
        con.execute(f"COPY corridor TO '{tmp_corridor_path.as_posix()}' WITH (FORMAT GDAL, DRIVER 'GeoJSON')")
        cells = compute_cells(tmp_corridor_path)

    return corridor_geom, cells


def index_quads_in_dir(quads_dir: Path, fallback_dir: Path | None, neatlines: dict) -> list[tuple]:
    """Read each quad's bounds once so we can test cell overlap without
    opening files repeatedly. Uses the real neatline (from `neatlines`,
    keyed by bare_key - see load_neatlines()) when a metadata match exists,
    since that's the quad's actual mapped area - the collar-inflated full
    raster extent would otherwise make cell-overlap tests match cells the
    quad has no real data in. Falls back to the full reprojected raster
    extent for any quad with no metadata match.

    Also validates each quad can actually be read: 3 of 1,654 quads
    (NC_Glade_Valley, VA_Marion, WV_Princeton) are corrupted on USGS's own S3
    bucket (LZW decode failures in a later strip, not strip 0) - confirmed
    genuine source-side corruption, not a truncated download on our end (a
    byte-exact re-download of NC_Glade_Valley still failed to read). A quick
    corner-pixel read isn't enough to catch this reliably (it missed 2 of the
    3 - see spike_raster_mosaic run on 2026-07-25), so this does a full-band
    read per quad instead - slower but definitive.

    fix_corrupted_quads.py (or fetch_and_mosaic_cell.py's reactive per-cell
    equivalent) replaces each bad quad with a substitute covering the same
    footprint, pulled from the live basemap.nationalmap.gov export service,
    stored in `fallback_dir` - those are included here alongside the bulk
    quads, not used to silently patch the originals in place.

    Takes explicit directories (rather than the module-level QUADS_DIR/
    FALLBACK_DIR constants) so the same logic serves both the whole-corridor
    path and a per-cell scratch directory - see index_quad_bounds() below
    for the whole-corridor wrapper."""
    index = []
    bad = []
    paths = list(quads_dir.glob("*/*.tif"))
    if fallback_dir is not None:
        paths += list(fallback_dir.glob("*.tif"))
    for path in paths:
        try:
            with rasterio.open(path) as src:
                full_bounds_4326 = transform_bounds(src.crs, DST_CRS, *src.bounds)
                src.read(1)  # full-band read - a corner-pixel read misses corruption in later strips
        except Exception as e:
            bad.append((path, str(e)))
            continue
        neatline = neatlines.get(bare_key(path.stem))
        index.append((path, neatline if neatline else full_bounds_4326, neatline))

    if bad:
        print(f"WARNING: {len(bad)} quad(s) failed to read and will be skipped:")
        for path, err in bad:
            print(f"  {path.name}: {err.splitlines()[-1] if err else err}")

    return index


def index_quad_bounds(neatlines):
    """Whole-corridor wrapper around index_quads_in_dir() - see that
    function for the real logic."""
    return index_quads_in_dir(QUADS_DIR, FALLBACK_DIR, neatlines)


def bounds_intersect(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def mosaic_one_cell(cell: tuple, matching: list[tuple], corridor_geom: dict):
    """Merge + corridor-clip whatever quads match this cell into one output
    array+rasterio-profile - the per-cell body of main()'s loop, extracted
    so fetch_and_mosaic_cell.py's per-cell CI path can call exactly the same
    logic. `matching` is a list of (path, neatline) tuples, same shape
    main()'s loop already filters `quad_index` down to.

    Returns (array, profile) on success - profile has every rasterio field
    needed to write the tile, including the corridor-clipped transform - or
    (None, reason) if this cell can't produce a tile. `reason` carries both
    the exact original per-cell log line (`print_reason`) and the exact
    original final-summary line (`summary_reason`) - these were two
    different strings in the pre-extraction code (one for the live progress
    log, one for the "Incomplete" recap at the end), preserved separately
    rather than collapsed into one, so the extraction doesn't change
    output."""
    if not matching:
        return None, {"print_reason": "no quads matched this cell at all", "summary_reason": "no matching quads"}

    vrts = []
    try:
        for path, neatline in matching:
            vrt = open_cropped_vrt(path, neatline)
            vrts.append(vrt)

        try:
            merged_arr, merged_transform = merge(vrts, bounds=cell, res=(TARGET_RES_DEG, TARGET_RES_DEG))
        except Exception as e:
            # Defensive: index_quads_in_dir() does a full-band read on every
            # quad (see that function's docstring for why a corner-pixel
            # check wasn't reliable enough), so this shouldn't trigger from
            # known corruption anymore - it's a safety net for anything
            # unexpected, not the primary defense.
            quads = [p.name for p, _ in matching]
            return None, {"print_reason": f"merge failed ({e}); quads: {quads}", "summary_reason": f"merge failed: {e}"}
    finally:
        for vrt in vrts:
            vrt.close()
            vrt.src_dataset.close()

    if merged_arr.size == 0 or not np.any(merged_arr):
        return None, {"print_reason": "merged result was empty/all-nodata", "summary_reason": "empty/all-nodata merge result"}

    profile = {
        "driver": "GTiff",
        "height": merged_arr.shape[1],
        "width": merged_arr.shape[2],
        "count": merged_arr.shape[0],
        "dtype": merged_arr.dtype,
        "crs": DST_CRS,
        "transform": merged_transform,
    }

    with MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            dataset.write(merged_arr)
            clipped_arr, clipped_transform = mask(dataset, [corridor_geom], crop=False, nodata=0)

    out_profile = profile.copy()
    out_profile["transform"] = clipped_transform
    return clipped_arr, out_profile


def main():
    print("Loading corridor + building grid cells...")
    corridor_geom, cells = load_corridor_and_cells()
    print(f"{len(cells)} cells intersect the corridor.")

    print("Loading quad neatlines from USGS metadata...")
    neatlines = load_neatlines()

    print("Indexing quad bounds (one header read per quad)...")
    quad_index = index_quad_bounds(neatlines)
    print(f"{len(quad_index)} quads indexed.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tiles_written = 0
    skipped_cells = []

    for i, cell in enumerate(cells):
        matching = [(path, neatline) for path, b, neatline in quad_index if bounds_intersect(b, cell)]
        arr, result = mosaic_one_cell(cell, matching, corridor_geom)
        if arr is None:
            print(f"  cell {i + 1}/{len(cells)}: SKIPPED - {result['print_reason']}")
            skipped_cells.append((i, result["summary_reason"]))
            continue

        out_path = OUT_DIR / f"tile_{i:03d}.tif"
        with rasterio.open(out_path, "w", **result) as dst:
            dst.write(arr)

        tiles_written += 1
        size_mb = out_path.stat().st_size / 1e6
        print(f"  cell {i + 1}/{len(cells)}: {len(matching)} quads -> {out_path.name} ({size_mb:.1f} MB)")

    # Completeness check: every corridor-intersecting cell must produce a
    # tile, or the background has real coverage gaps a hiker could hit.
    # Each problem string is formatted "cell {i+1}: {reason}" so
    # fail_if_incomplete's per-line output matches this script's original
    # inline check exactly; only the summary header's wording now comes from
    # the shared helper, like every other script that adopts it (see
    # lib/completeness.py).
    problems = [f"cell {i + 1}: {reason}" for i, reason in skipped_cells]
    if problems:
        print()  # blank-line separator before the summary, matching the original formatting
    fail_if_incomplete(problems, label="Incomplete raster mosaic")

    print(f"\nDone. {tiles_written} clipped background tiles written -> {OUT_DIR}")


if __name__ == "__main__":
    main()
