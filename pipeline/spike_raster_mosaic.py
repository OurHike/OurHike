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
import sys
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

CORRIDOR_PATH = Path(__file__).parent / "data" / "spike" / "corridor.geojson"
QUADS_DIR = Path(__file__).parent / "data" / "raw" / "topo_quads"
FALLBACK_DIR = Path(__file__).parent / "data" / "raw" / "topo_quads_fallback"
OUT_DIR = Path(__file__).parent / "data" / "processed" / "topo_background"
METADATA_CSV_PATH = Path(__file__).parent / "data" / "raw" / "topo_metadata" / "ustopo_current.csv"

CELL_DEGREES = 1.0
TARGET_RES_DEG = 0.0001  # ~11m/pixel at these latitudes - plenty for a phone background map
DST_CRS = "EPSG:4326"


def load_neatlines():
    """Maps each quad's bare key (see fetch_topo_quads.bare_key) to its real
    neatline bounds (west, south, east, north) from USGS's own metadata CSV -
    the true mapped area, not the collar-inflated raster extent."""
    neatlines = {}
    with open(METADATA_CSV_PATH, newline="", encoding="utf-8") as f:
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
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE corridor AS SELECT * FROM ST_Read('{CORRIDOR_PATH.as_posix()}')")
    bbox = con.execute("SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) FROM corridor").fetchone()
    corridor_geom = json.loads(con.execute("SELECT ST_AsGeoJSON(geom) FROM corridor").fetchone()[0])

    xmin, ymin, xmax, ymax = bbox
    cells = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            cx0, cy0 = x, y
            cx1, cy1 = min(x + CELL_DEGREES, xmax), min(y + CELL_DEGREES, ymax)
            hit = con.execute(f"""
                SELECT EXISTS (SELECT 1 FROM corridor WHERE ST_Intersects(geom, ST_MakeEnvelope({cx0}, {cy0}, {cx1}, {cy1})))
            """).fetchone()[0]
            if hit:
                cells.append((cx0, cy0, cx1, cy1))
            y += CELL_DEGREES
        x += CELL_DEGREES
    return corridor_geom, cells


def index_quad_bounds(neatlines):
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

    fix_corrupted_quads.py replaces each bad quad with a substitute covering
    the same footprint, pulled from the live basemap.nationalmap.gov export
    service, stored in FALLBACK_DIR - those are included here alongside the
    bulk quads, not used to silently patch the originals in place."""
    index = []
    bad = []
    paths = list(QUADS_DIR.glob("*/*.tif")) + list(FALLBACK_DIR.glob("*.tif"))
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


def bounds_intersect(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


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
        if not matching:
            print(f"  cell {i + 1}/{len(cells)}: SKIPPED - no quads matched this cell at all")
            skipped_cells.append((i, "no matching quads"))
            continue

        vrts = []
        try:
            for path, neatline in matching:
                vrt = open_cropped_vrt(path, neatline)
                vrts.append(vrt)

            try:
                merged_arr, merged_transform = merge(vrts, bounds=cell, res=(TARGET_RES_DEG, TARGET_RES_DEG))
            except Exception as e:
                # Defensive: index_quad_bounds() now does a full-band read on
                # every quad (see that function's docstring for why a
                # corner-pixel check wasn't reliable enough), so this
                # shouldn't trigger from known corruption anymore - it's a
                # safety net for anything unexpected, not the primary defense.
                print(f"  cell {i + 1}/{len(cells)}: SKIPPED - merge failed ({e}); quads: {[p.name for p, _ in matching]}")
                skipped_cells.append((i, f"merge failed: {e}"))
                continue
        finally:
            for vrt in vrts:
                vrt.close()
                vrt.src_dataset.close()

        if merged_arr.size == 0 or not np.any(merged_arr):
            print(f"  cell {i + 1}/{len(cells)}: SKIPPED - merged result was empty/all-nodata")
            skipped_cells.append((i, "empty/all-nodata merge result"))
            continue

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

        out_path = OUT_DIR / f"tile_{i:03d}.tif"
        out_profile = profile.copy()
        out_profile["transform"] = clipped_transform
        with rasterio.open(out_path, "w", **out_profile) as dst:
            dst.write(clipped_arr)

        tiles_written += 1
        size_mb = out_path.stat().st_size / 1e6
        print(f"  cell {i + 1}/{len(cells)}: {len(matching)} quads -> {out_path.name} ({size_mb:.1f} MB)")

    # Completeness check: every corridor-intersecting cell must produce a
    # tile, or the background has real coverage gaps a hiker could hit.
    if skipped_cells:
        print(f"\nIncomplete: {len(skipped_cells)}/{len(cells)} cells produced no tile:")
        for i, reason in skipped_cells:
            print(f"  cell {i + 1}: {reason}")
        sys.exit(1)

    print(f"\nDone. {tiles_written} clipped background tiles written -> {OUT_DIR}")


if __name__ == "__main__":
    main()
