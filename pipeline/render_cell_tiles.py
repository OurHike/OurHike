"""Render one fan-out cell's share of the native-resolution raster tiles -
the per-cell half of #191's rebuild, replacing fetch_and_mosaic_cell.py's
11 m mosaics with tiles warped once from the quads' native 2.032 m pixels.

WHAT ONE JOB PRODUCES

  cell_tiles_<i>.pmtiles   every z11-z14 tile this cell OWNS (tile centre
                           inside the cell's bbox, nearest cell when the
                           centre escapes the grid - lib/raster_tiles.py's
                           owner_index, the fan-out's dedup rule), rendered
                           by the same module's warp-once path. z14 only
                           within the five-mile near-trail band (issue
                           #191's tiered shape).
  overview_<i>.tif         the cell's assigned quads averaged from native
                           onto a 24 m mercator grid - what assemble
                           renders z0-z10 from, so the far-out zooms never
                           need raw quads on one runner.
  receipt_<i>.json         the owned tile list and what became of each, so
                           assemble can verify the union is exactly the
                           corridor's enumeration - a missing artifact and
                           a cell that owned nothing must not look alike.

WHY THE FETCH SET IS WIDER THAN THE CELL'S QUAD LIST

Ownership decides who WRITES a tile, not what pixels it needs: a z11 tile
whose centre sits just inside this cell spans ~15 km, reaching well into
the neighbouring cells' quads. So the job fetches every corridor quad whose
bounds intersect any OWNED tile - plus the cell's own assigned list, which
the overview needs even where an edge sliver owns no tiles. Seams between
cells cannot exist by construction: whichever job owns a border tile holds
both sides' quads.

Corruption handling, completeness, and scratch layout all mirror
fetch_and_mosaic_cell.py, whose per-quad fetch/fix seams this reuses.
"""

import argparse
import json
from pathlib import Path

import rasterio
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from pyproj import Transformer
from rasterio.warp import transform_bounds
from shapely.geometry import shape
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

from fetch_and_mosaic_cell import load_cell
from fetch_topo_quads import fetch_quads_for_cell, resolve_state_index
from fix_corrupted_quads import fix_quad
from lib.corridor_grid import load_quad_bounds
from lib.raster_tiles import (
    NATIVE_MIN_ZOOM,
    encode_webp,
    mask_outside,
    neatline_box_merc,
    owner_index,
    render_overview,
    render_tile_from_quads,
    tiles_intersecting_geom,
)
from lib.tiling import tile_bounds_merc
from spike_raster_mosaic import bounds_intersect, index_quads_in_dir, load_neatlines

ROOT = Path(__file__).parent
DEFAULT_CELLS_JSON = ROOT / "data" / "raw" / "cells.json"
DEFAULT_METADATA_CSV = ROOT / "data" / "raw" / "topo_metadata" / "ustopo_current.csv"
DEFAULT_CORRIDOR = ROOT / "data" / "raw" / "corridor.geojson"
DEFAULT_CENTERLINE = ROOT / "data" / "raw" / "centerline.geojson"
DEFAULT_OUT_DIR = ROOT / "data" / "processed" / "raster_cells"

MAX_ZOOM = 14
# z14 ships only where hikers walk: within five miles of the centerline.
# Corridor-wide z14 measured ~4.6-4.9 GB in #191's research; the band plus
# the z13 base is ~1.8 GB - the difference between an optional sheet someone
# downloads and one nobody does.
BAND_ZOOM = 14
BAND_METERS = 5 * 1609.344

MERC_CRS = "EPSG:3857"
GEO_CRS = "EPSG:4326"


def load_geom_merc(path: Path):
    """A GeoJSON file's (unioned) geometry in EPSG:3857. Accepts a bare
    geometry, Feature, or FeatureCollection - the corridor and centerline
    artifacts are FeatureCollections."""
    parsed = json.loads(path.read_text())
    if parsed.get("type") == "FeatureCollection":
        geoms = [shape(f["geometry"]) for f in parsed["features"]]
        geom = unary_union(geoms)
    elif parsed.get("type") == "Feature":
        geom = shape(parsed["geometry"])
    else:
        geom = shape(parsed)
    to_merc = Transformer.from_crs(GEO_CRS, MERC_CRS, always_xy=True)
    return shp_transform(to_merc.transform, geom)


def owned_tiles(cell_index, cell_bboxes, corridor_merc, band_merc):
    """Every (z, x, y) this cell writes: corridor-intersecting below
    BAND_ZOOM, band-intersecting at it - filtered to tiles owner_index
    assigns to this cell. Needs the WHOLE grid, not just this cell's bbox:
    a tile whose centre falls inside no cell goes to the nearest one, and
    "nearest" is only answerable with every cell in hand."""
    owned = []
    for z in range(NATIVE_MIN_ZOOM, MAX_ZOOM + 1):
        region = band_merc if z >= BAND_ZOOM else corridor_merc
        for x, y in tiles_intersecting_geom(region, z):
            t_bounds = transform_bounds(MERC_CRS, GEO_CRS, *tile_bounds_merc(z, x, y))
            if owner_index(cell_bboxes, t_bounds) == cell_index:
                owned.append((z, x, y))
    return owned


def quads_for_tiles(quad_bounds: dict, tiles) -> set:
    """Product filenames whose bounds intersect any of the tiles - the pixels
    an owned tile needs, wherever the quad was assigned."""
    tile_bounds = [transform_bounds(MERC_CRS, GEO_CRS, *tile_bounds_merc(z, x, y)) for z, x, y in tiles]
    return {pf for pf, bounds in quad_bounds.items() if any(bounds_intersect(tuple(bounds), tb) for tb in tile_bounds)}


def fetch_quads(product_filenames, metadata_csv: Path, scratch_dir: Path):
    """fetch_and_mosaic_cell.run_cell's fetch/fix/verify sequence, over this
    job's own quad set. Returns index_quads_in_dir's verified
    (path, bounds_4326, neatline_4326) triples, or raises when any requested
    quad cannot be had - one of ~51 unattended jobs must fail loudly, not
    ship a coverage hole."""
    quads_dir = scratch_dir / "quads"
    fallback_dir = scratch_dir / "fallback"
    quads_dir.mkdir(parents=True, exist_ok=True)
    fallback_dir.mkdir(parents=True, exist_ok=True)

    ordered = sorted(product_filenames)
    states = sorted({pf.split("_", 1)[0] for pf in ordered})
    print(f"fetching {len(ordered)} quads across {len(states)} state(s): {states}")
    state_index = resolve_state_index(states)

    manifest: dict = {}
    results = fetch_quads_for_cell(ordered, state_index, quads_dir, manifest)
    for product_filename, result in zip(ordered, results):
        if result["status"] == "corrupted":
            print(f"  {product_filename}: corrupted after download, attempting inline fix...")
            fix_result = fix_quad(product_filename, result["path"], metadata_csv, fallback_dir)
            if fix_result["status"] == "failed":
                print(f"  {product_filename}: fix failed")
        elif result["status"] == "unmatched":
            print(f"  {product_filename}: UNMATCHED ({result.get('reason')})")

    neatlines = load_neatlines(metadata_csv)
    quad_index = index_quads_in_dir(quads_dir, fallback_dir, neatlines)
    if len(quad_index) < len(ordered):
        missing = len(ordered) - len(quad_index)
        raise RuntimeError(
            f"{missing}/{len(ordered)} quads did not survive fetch+verify (see per-quad "
            "warnings above) - refusing to render with a silent coverage hole"
        )
    return quad_index


def render_cell(
    cell_index: int,
    cells_json: Path,
    metadata_csv: Path,
    corridor_path: Path,
    centerline_path: Path,
    out_dir: Path,
    scratch_dir: Path,
):
    cell = load_cell(cells_json, cell_index)
    cell_bbox = tuple(cell["bbox"])
    # owner_index positions cells by list index; build_cells_manifest.py
    # numbers them the same way, and this refuses a manifest where that has
    # stopped being true rather than silently mis-assigning every tile.
    cells = json.loads(cells_json.read_text())["cells"]
    if [c["index"] for c in cells] != list(range(len(cells))):
        raise SystemExit(f"{cells_json} cell indices are not 0..n-1 in order - ownership would be misassigned.")
    cell_bboxes = [tuple(c["bbox"]) for c in cells]

    corridor_merc = load_geom_merc(corridor_path)
    band_merc = load_geom_merc(centerline_path).buffer(BAND_METERS)

    owned = owned_tiles(cell_index, cell_bboxes, corridor_merc, band_merc)
    print(f"cell {cell_index}: owns {len(owned)} tiles (z{NATIVE_MIN_ZOOM}-{MAX_ZOOM})")

    quad_bounds = load_quad_bounds(corridor_path, metadata_csv)
    wanted = quads_for_tiles(quad_bounds, owned) | set(cell["quads"])
    quad_index = fetch_quads(wanted, metadata_csv, scratch_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Open once for the whole job; a cell renders thousands of tiles from
    # the same few dozen quads. The neatline mask travels with each dataset
    # in mercator, ready for the per-tile geometry_mask.
    datasets = []
    try:
        by_path = []
        for path, bounds, neatline in quad_index:
            ds = rasterio.open(path)
            datasets.append(ds)
            by_path.append((ds, tuple(bounds), neatline_box_merc(neatline) if neatline else None))

        written = []
        empty = []
        tiles_path = out_dir / f"cell_tiles_{cell_index}.pmtiles"
        with write(str(tiles_path)) as writer:
            for z, x, y in sorted(owned, key=lambda t: zxy_to_tileid(*t)):
                t_bounds_4326 = transform_bounds(MERC_CRS, GEO_CRS, *tile_bounds_merc(z, x, y))
                matching = [(ds, nl_merc) for ds, bounds, nl_merc in by_path if bounds_intersect(bounds, t_bounds_4326)]
                arr = render_tile_from_quads(z, x, y, matching) if matching else None
                if arr is not None:
                    arr = mask_outside(arr, corridor_merc, z, x, y)
                    if not arr.any():
                        arr = None
                if arr is None:
                    empty.append([z, x, y])
                    continue
                writer.write_tile(zxy_to_tileid(z, x, y), encode_webp(arr))
                written.append([z, x, y])
            if written:
                writer.finalize(cell_header(cell_bbox), {"name": f"OurHike raster cell {cell_index}", "format": "webp"})
        if not written:
            # pmtiles cannot hold zero tiles; the receipt is what tells
            # assemble this was "owned nothing real", not a lost artifact.
            tiles_path.unlink(missing_ok=True)
            tiles_path = None

        overview_path = out_dir / f"overview_{cell_index}.tif"
        write_overview(cell_bbox, by_path, corridor_merc, overview_path)
    finally:
        for ds in datasets:
            ds.close()

    receipt = {
        "cell": cell_index,
        "owned": sorted(owned),
        "written": sorted(map(tuple, written)),
        "empty": sorted(map(tuple, empty)),
        "tiles": tiles_path.name if tiles_path else None,
        "overview": overview_path.name,
    }
    receipt_path = out_dir / f"receipt_{cell_index}.json"
    receipt_path.write_text(json.dumps(receipt))
    print(f"cell {cell_index}: {len(written)} tiles written, {len(empty)} empty, overview -> {overview_path.name}")


def write_overview(cell_bbox_4326, by_path, corridor_merc, out_path: Path):
    """The cell's ground, averaged once from native to the 24 m grid and
    corridor-masked - assemble's source for z0-10. Selected by bounds
    intersection with the cell rather than by the manifest's name list:
    intersection IS what quad assignment meant, and the fetched files carry
    dated names the manifest's product filenames only prefix."""
    from rasterio.features import geometry_mask

    quads = [(ds, nl_merc) for ds, bounds, nl_merc in by_path if bounds_intersect(bounds, cell_bbox_4326)]

    bounds_merc = transform_bounds(GEO_CRS, MERC_CRS, *cell_bbox_4326)
    arr, transform = render_overview(bounds_merc, quads)

    outside = geometry_mask([corridor_merc.__geo_interface__], out_shape=arr.shape[1:], transform=transform)
    arr[:, outside] = 0

    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        width=arr.shape[2],
        height=arr.shape[1],
        count=3,
        dtype="uint8",
        crs=MERC_CRS,
        transform=transform,
        nodata=0,
        compress="deflate",
        tiled=True,
    ) as dst:
        dst.write(arr)


def cell_header(cell_bbox_4326):
    west, south, east, north = cell_bbox_4326
    return {
        "tile_type": TileType.WEBP,
        "tile_compression": Compression.NONE,
        "min_lon_e7": int(west * 1e7),
        "min_lat_e7": int(south * 1e7),
        "max_lon_e7": int(east * 1e7),
        "max_lat_e7": int(north * 1e7),
        "center_lon_e7": int((west + east) / 2 * 1e7),
        "center_lat_e7": int((south + north) / 2 * 1e7),
        "center_zoom": NATIVE_MIN_ZOOM,
    }


def main(args: argparse.Namespace):
    scratch = args.scratch_dir or (ROOT / "data" / "raw" / f"topo_quads_cell_{args.cell_index}")
    render_cell(args.cell_index, args.cells_json, args.metadata_csv, args.corridor, args.centerline, args.out_dir, scratch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cell-index", type=int, required=True)
    parser.add_argument("--cells-json", type=Path, default=DEFAULT_CELLS_JSON)
    parser.add_argument("--metadata-csv", type=Path, default=DEFAULT_METADATA_CSV)
    parser.add_argument("--corridor", type=Path, default=DEFAULT_CORRIDOR)
    parser.add_argument("--centerline", type=Path, default=DEFAULT_CENTERLINE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--scratch-dir", type=Path, default=None)
    main(parser.parse_args())
