"""Export the corridor-clipped background raster (see spike_raster_mosaic.py)
as a single PMTiles archive - the actual web map tile pyramid MapLibre GL JS
reads directly in the browser, no tile server required (see
TECHNICAL_ARCHITECTURE.md's "Export" pipeline step).

Source: the 51 already-mosaicked/clipped/reprojected GeoTIFF cells in
data/processed/topo_background/ (EPSG:4326, ~11m/pixel) - not the raw 1,654
USGS quads, which are already folded into those cells. No corruption re-check
is needed here (unlike fetch_topo_quads.py/spike_raster_mosaic.py): these are
our own already-validated output, not a fresh download from USGS.

Format choices, backed by real measurements on this project's own data (see
README.md's "Exporting the background as PMTiles" section for the numbers):
- 512x512px tiles, WebP quality 80 - both chosen to minimize total download
  size, not arbitrary defaults. 512px tiles compress better per unit ground
  area than 256px (more shared context per image, less per-file header
  overhead - MapLibre reads these via the `tileSize: 512` raster option).
  WebP came out ~7-8x smaller than PNG on real sample tiles with no visible
  quality loss for a background/context basemap - the safety-relevant POI
  data is separate vector GeoJSON, untouched by this lossy step.
- Zoom 6-12 in this 512px scheme (equivalent in ground resolution to 256px
  zoom 7-13: worldsize/(2^z*512) == worldsize/(2^(z+1)*256)). Zoom 13 was the
  first real run's max zoom (matching the source's native ~11m/pixel
  resolution exactly) but turned out to be 73% of the entire archive's bytes
  on its own (868MB of 1.18GB) for a resolution gain over zoom 12 that a
  background/context layer doesn't need - trimming it cuts the whole-corridor
  download to ~314MB, a ~73% reduction, for a still-detailed ~19m/pixel
  result. See ROADMAP.md's Phase 2 "quality/size tradeoff in settings" item -
  the plan is to eventually let hikers choose 11/12/13 themselves rather than
  bake in one fixed default forever.

Corridor-vs-tile intersection is done with shapely in a plain Python loop,
not one DuckDB query per candidate tile - an earlier attempt at the latter
was killed after 2 minutes with zero output; loading the corridor polygon
once and testing intersections directly finishes in seconds.
"""

import argparse
import io
import json
from pathlib import Path

import duckdb
import numpy as np
import rasterio
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from rasterio.merge import merge
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling, transform_bounds
from shapely.geometry import box, shape

from lib.completeness import count_problems, fail_if_incomplete
from lib.corridor import build_corridor
from lib.tiling import tile_bounds_merc, tile_range_for_bounds
from spike_raster_mosaic import bounds_intersect

ROOT = Path(__file__).parent
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
CELLS_DIR = ROOT / "data" / "processed" / "topo_background"
OUT_PATH = ROOT / "data" / "processed" / "background.pmtiles"

# Zoom 0, not 6, since 2026-08-05 (#216).
#
# At 6 the archive had no tiles at the zoom the app actually OPENS at. The
# client frames the whole trail on first run - Springer to Katahdin, which fits
# at roughly z3.8 on a phone and z4.9 on a desktop - so a hiker with a complete
# 314 MB download and the offline background selected was shown flat paper
# every single launch, and had to zoom in two levels to discover the map was
# there at all. Nothing in either codebase reconciled the two numbers; they
# were set three months apart and never compared.
#
# The cost is close to nothing. Tile count grows by the z0..z5 tiles that
# intersect a 30-mile corridor - tens of tiles against the tens of thousands
# already written - and export_dem.py has shipped MIN_ZOOM = 0 all along, so
# this also ends a disagreement between two exports of the same corridor that
# no comment ever defended.
#
# Worth knowing before the next real run: at z0 the corridor is about 0.8 px
# wide, though still ~22 px long, so it renders as a hairline rather than
# vanishing. The completeness gate at the foot of main() is what will say so
# for certain - it requires every source cell to contribute a written tile at
# EVERY tier, so an all-nodata bottom tier fails the export loudly rather than
# shipping a hole. That check has not been run against the real 14 GB source
# here; it needs a genuine export.
MIN_ZOOM = 0
MAX_ZOOM = 12
TILE_PX = 512
WEBP_QUALITY = 80
MERC_CRS = "EPSG:3857"
GEOGRAPHIC_CRS = "EPSG:4326"


def load_corridor():
    """Returns (bounds_4326, corridor_merc) - the corridor's native lon/lat
    bounds (for the PMTiles header) and its EPSG:3857 shapely geometry (for
    fast tile-intersection tests). Built fresh from CENTERLINE_PATH via
    lib/corridor.py's build_corridor() on every call - deliberately never
    read from data/spike/corridor.geojson, which is stale proof-of-concept
    output (see lib/corridor.py's own docstring for the full story)."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    build_corridor(con, CENTERLINE_PATH)
    bounds_4326 = con.execute("SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom) FROM corridor").fetchone()
    gj = con.execute(f"""
        SELECT ST_AsGeoJSON(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{MERC_CRS}', always_xy := true))
        FROM corridor
    """).fetchone()[0]
    return bounds_4326, shape(json.loads(gj))


def index_cells():
    """Each source cell's EPSG:4326 bounds and path."""
    index = []
    for path in sorted(CELLS_DIR.glob("tile_*.tif")):
        with rasterio.open(path) as src:
            index.append((path, src.bounds))
    return index


def find_export_tiles(corridor_merc):
    """Every (z, x, y) XYZ tile at MIN_ZOOM..MAX_ZOOM whose bounds actually
    intersect the corridor polygon (not just its bounding box)."""
    tiles = []
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        x0, x1, y0, y1 = tile_range_for_bounds(corridor_merc.bounds, z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                if corridor_merc.intersects(box(*tile_bounds_merc(z, x, y))):
                    tiles.append((z, x, y))
    return tiles


def matching_cells(tile_bounds_4326, cell_index):
    """Which indexed source cells overlap a tile's EPSG:4326 bounds."""
    return [path for path, bounds in cell_index if bounds_intersect(tuple(bounds), tile_bounds_4326)]


def render_tile(z, x, y, cell_index):
    """Reproject whichever source cell(s) cover this tile into a
    TILE_PX x TILE_PX EPSG:3857 array. Returns (None, matching) if there's no
    real data (all-nodata) - those tiles are skipped entirely, not written
    empty. `matching` is returned either way so callers can track per-cell
    export coverage without recomputing the same lookup.

    Uses rasterio.merge.merge() (same as spike_raster_mosaic.py) rather than
    calling reproject() once per matching cell into a shared array - an
    earlier version did that, and a test with two adjacent cells proved it
    silently wrong: each reproject() call resets the *entire* destination
    array to nodata before painting its own source, so whichever cell was
    processed last completely erased every earlier cell's contribution
    instead of only filling in its own footprint. merge() composites
    multiple sources into one array correctly instead."""
    merc_bounds = tile_bounds_merc(z, x, y)
    tile_bounds_4326 = transform_bounds(MERC_CRS, GEOGRAPHIC_CRS, *merc_bounds)
    matching = matching_cells(tile_bounds_4326, cell_index)
    if not matching:
        return None, matching

    res = (merc_bounds[2] - merc_bounds[0]) / TILE_PX
    srcs, vrts = [], []
    try:
        for path in matching:
            src = rasterio.open(path)
            srcs.append(src)
            vrts.append(WarpedVRT(src, crs=MERC_CRS))
        dst, _ = merge(vrts, bounds=merc_bounds, res=(res, res), resampling=Resampling.bilinear, indexes=[1, 2, 3])
    finally:
        for vrt in vrts:
            vrt.close()
        for src in srcs:
            src.close()

    assert dst.shape == (3, TILE_PX, TILE_PX), f"merge() produced {dst.shape}, expected (3, {TILE_PX}, {TILE_PX})"
    if not np.any(dst):
        return None, matching
    return dst, matching


def encode_webp(arr) -> bytes:
    """RGBA, not RGB - the alpha channel is what stops the corridor being a
    black rectangle.

    The corridor is a 30-mile ribbon and every tile is a square, so most of
    most tiles is outside it. mosaic_one_cell() masks that ground with
    nodata=0 and merge() fills gaps with 0, and written as RGB those pixels
    are not "nothing", they are the colour black. Measured on a real z6 tile
    before this change: 99% black. Fine while the map opened zoomed in over
    the corridor, and immediately obvious once it opened on the whole trail.

    Alpha is derived from the same all-zero convention the rest of this
    pipeline already uses for nodata - the `not np.any(dst)` check in
    render_tile() above decides a tile is empty exactly this way.

    Honest limitation: a source pixel that is genuinely pure black in all
    three channels becomes transparent. Scanned topo ink is essentially never
    exactly 0 after bilinear resampling, and one see-through pixel is a far
    smaller wrong than a black continent.
    """
    rgb = np.moveaxis(arr, 0, -1)
    alpha = np.where(rgb.any(axis=-1), 255, 0).astype("uint8")
    img = Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY)
    return buf.getvalue()


def build_header(bounds_4326):
    min_lon, min_lat, max_lon, max_lat = bounds_4326
    return {
        "tile_type": TileType.WEBP,
        "tile_compression": Compression.NONE,
        "min_lon_e7": int(min_lon * 1e7),
        "min_lat_e7": int(min_lat * 1e7),
        "max_lon_e7": int(max_lon * 1e7),
        "max_lat_e7": int(max_lat * 1e7),
        "center_lon_e7": int((min_lon + max_lon) / 2 * 1e7),
        "center_lat_e7": int((min_lat + max_lat) / 2 * 1e7),
        "center_zoom": MIN_ZOOM,
    }


def main():
    print("Building corridor from centerline...")
    bounds_4326, corridor_merc = load_corridor()

    print("Indexing source cells...")
    cell_index = index_cells()
    print(f"{len(cell_index)} source cells.")
    if not cell_index:
        raise SystemExit(f"No source cells found in {CELLS_DIR} - run spike_raster_mosaic.py first.")

    print(f"Enumerating export tiles (zoom {MIN_ZOOM}-{MAX_ZOOM})...")
    tiles = sorted(find_export_tiles(corridor_merc), key=lambda t: zxy_to_tileid(*t))
    print(f"{len(tiles)} candidate tiles intersect the corridor.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = empty = 0
    # Per-zoom, not just at MAX_ZOOM: a cell can render fine at the top zoom
    # tier yet come back all-nodata at some lower zoom (z6..z11, used for
    # trip-overview zoom-out) - tracking coverage only at MAX_ZOOM made that
    # kind of gap structurally uncatchable for the other 6 zoom tiers this
    # file ships.
    cells_covered_by_zoom = {z: set() for z in range(MIN_ZOOM, MAX_ZOOM + 1)}

    with write(str(OUT_PATH)) as writer:
        for i, (z, x, y) in enumerate(tiles, 1):
            arr, matching = render_tile(z, x, y, cell_index)
            if arr is None:
                empty += 1
            else:
                writer.write_tile(zxy_to_tileid(z, x, y), encode_webp(arr))
                written += 1
                cells_covered_by_zoom[z].update(matching)
            if i % 2000 == 0 or i == len(tiles):
                print(f"  {i}/{len(tiles)} processed ({written} written, {empty} empty/skipped)")

        writer.finalize(build_header(bounds_4326), {"name": "OurHike background", "format": "webp"})

    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"\nDone. {written} tiles written, {empty} empty/skipped -> {OUT_PATH} ({size_mb:.1f} MB)")

    # Coverage check: every source cell should contribute to at least one
    # written tile at EVERY zoom tier (MIN_ZOOM..MAX_ZOOM inclusive), not just
    # the top one, or the export silently dropped real corridor coverage at
    # that zoom - mirrors the completeness check in spike_raster_mosaic.py/
    # export_poi.py, via the same shared lib/completeness.py gate.
    all_cells = sorted({path for path, _ in cell_index}, key=lambda p: p.name)
    counts = {
        f"zoom {z}: {path.name}": int(path in cells_covered_by_zoom[z])
        for z in range(MIN_ZOOM, MAX_ZOOM + 1)
        for path in all_cells
    }
    problems = count_problems(counts)
    fail_if_incomplete(problems, label="Incomplete background export")


if __name__ == "__main__":
    # Kept outside main() deliberately - main() is called directly (with
    # MIN_ZOOM/MAX_ZOOM/OUT_PATH monkeypatched) by the test suite, and
    # argparse.parse_args() with no explicit argv reads sys.argv, which
    # would try to parse pytest's own command-line arguments if this lived
    # inside main() instead.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM, help=f"Minimum zoom level (default: {MIN_ZOOM})")
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=MAX_ZOOM,
        help=f"Maximum zoom level (default: {MAX_ZOOM}) - e.g. --max-zoom=13 rebuilds the full-detail "
        "archive for the future per-user zoom-choice feature (see ROADMAP.md)",
    )
    parser.add_argument("--out", type=Path, default=OUT_PATH, help=f"Output .pmtiles path (default: {OUT_PATH})")
    args = parser.parse_args()
    MIN_ZOOM, MAX_ZOOM, OUT_PATH = args.min_zoom, args.max_zoom, args.out
    main()
