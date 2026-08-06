"""Assemble the per-cell native-tile renders into the shipping raster
archives - the reconvergence half of #191's rebuild, replacing
export_pmtiles.py's render-from-11m-cells.

INPUTS (data/processed/raster_cells/, one set per fan-out cell)
  cell_tiles_<i>.pmtiles   the z11-14 tiles the cell owned and wrote
  overview_<i>.tif         24 m corridor-masked mercator overview
  receipt_<i>.json         owned/written/empty tile lists

WHAT IT WRITES - four tiers, all z0 up (the #216 rule: tiles at the zoom
the app opens at), low zooms rendered here from the overviews, native
zooms streamed through a k-way merge of the cell archives:

  background_z11.pmtiles   Light      z0-11
  background.pmtiles       Standard   z0-12
  background_z13.pmtiles   Fine       z0-13
  quad_sheet_z14.pmtiles   the optional USGS sheet: z0-13 corridor-wide
                           plus z14 within five miles of the trail

HONESTY GATES, because 51 unattended jobs reconverge here:
  - every cell in cells.json must have a receipt; a receipt whose tiles
    file is missing (but wrote tiles) is a lost artifact, not a quiet gap
  - the union of every receipt's written+empty must be EXACTLY the
    corridor's own tile enumeration, no overlaps - the ownership rule,
    verified rather than trusted
  - every overview must contribute to a written tile at every low zoom,
    the same per-cell-per-zoom gate export_pmtiles.py held
"""

import argparse
import heapq
import json
from pathlib import Path

import rasterio
from pmtiles.reader import MmapSource, all_tiles
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from rasterio.enums import Resampling
from rasterio.merge import merge

from lib.completeness import count_problems, fail_if_incomplete
from lib.raster_tiles import (
    NATIVE_MIN_ZOOM,
    OVERVIEW_MAX_ZOOM,
    TILE_PX,
    encode_webp,
    tiles_intersecting_geom,
)
from lib.tiling import tile_bounds_merc
from render_cell_tiles import BAND_METERS, BAND_ZOOM, MAX_ZOOM, load_geom_merc
from spike_raster_mosaic import bounds_intersect

ROOT = Path(__file__).parent
DEFAULT_CELLS_DIR = ROOT / "data" / "processed" / "raster_cells"
DEFAULT_CORRIDOR = ROOT / "data" / "raw" / "corridor.geojson"
DEFAULT_CENTERLINE = ROOT / "data" / "raw" / "centerline.geojson"
DEFAULT_CELLS_JSON = ROOT / "data" / "raw" / "cells.json"
OUT_DIR = ROOT / "data" / "processed"

MIN_ZOOM = 0

TIERS = [
    ("background_z11.pmtiles", 11),
    ("background.pmtiles", 12),
    ("background_z13.pmtiles", 13),
    ("quad_sheet_z14.pmtiles", MAX_ZOOM),
]


def load_receipts(cells_json: Path, cells_dir: Path) -> list[dict]:
    cells = json.loads(cells_json.read_text())["cells"]
    receipts = []
    missing = []
    for cell in cells:
        path = cells_dir / f"receipt_{cell['index']}.json"
        if not path.exists():
            missing.append(cell["index"])
            continue
        receipts.append(json.loads(path.read_text()))
    if missing:
        raise SystemExit(f"No receipt for cell(s) {missing} - a lost render job, not a quiet gap.")
    return receipts


def verify_receipts(receipts: list[dict], corridor_merc, band_merc, cells_dir: Path):
    """The ownership rule, checked rather than trusted: the union of what
    every cell owned must be exactly this corridor's enumeration, with no
    tile owned twice - and every receipt that wrote tiles must still have
    its archive."""
    owned = [tuple(t) for r in receipts for t in r["owned"]]
    if len(owned) != len(set(owned)):
        raise SystemExit("Overlapping ownership between cells - the same tile was rendered twice.")

    expected = set()
    for z in range(NATIVE_MIN_ZOOM, MAX_ZOOM + 1):
        region = band_merc if z >= BAND_ZOOM else corridor_merc
        expected.update((z, x, y) for x, y in tiles_intersecting_geom(region, z))
    if set(owned) != expected:
        extra = len(set(owned) - expected)
        absent = len(expected - set(owned))
        raise SystemExit(
            f"Cell ownership does not tile the corridor: {absent} expected tiles unowned, "
            f"{extra} owned outside the enumeration. The cells were cut against a different "
            "corridor than this assemble is using."
        )

    for r in receipts:
        if r["written"] and r["tiles"] is None:
            raise SystemExit(f"Receipt for cell {r['cell']} claims tiles but names no archive.")
        if r["tiles"] is not None and not (cells_dir / r["tiles"]).exists():
            raise SystemExit(f"Cell {r['cell']}'s archive {r['tiles']} is missing.")


def native_tile_stream(receipts: list[dict], cells_dir: Path, max_zoom: int):
    """Every cell's written tiles, merged into one ascending-tileid stream -
    the order pmtiles' writer requires. Each cell archive is already sorted;
    heapq.merge does the k-way zip without holding tiles in memory."""
    handles = []
    streams = []
    for r in receipts:
        if r["tiles"] is None:
            continue
        f = open(cells_dir / r["tiles"], "rb")
        handles.append(f)
        source = MmapSource(f)
        streams.append(((zxy_to_tileid(z, x, y), (z, x, y), data) for (z, x, y), data in all_tiles(source)))
    try:
        for _tileid, (z, x, y), data in heapq.merge(*streams, key=lambda item: item[0]):
            if z <= max_zoom:
                yield (z, x, y), data
    finally:
        for f in handles:
            f.close()


def index_overviews(cells_dir: Path):
    index = []
    for path in sorted(cells_dir.glob("overview_*.tif")):
        with rasterio.open(path) as src:
            index.append((path, tuple(src.bounds)))
    return index


def render_low_zoom_tiles(corridor_merc, overview_index):
    """z0-10 from the 24 m overviews: the one further decimation the far-out
    zooms take, with `average` - see lib/raster_tiles.py's overview note.
    Returns ({(z, x, y): webp_bytes}, {(zoom, path): contributed}) - small
    enough to hold (a 30-mile ribbon is tens of tiles per low zoom), and
    cached so the four tiers encode each low tile once."""
    tiles = {}
    contributions = {}
    srcs = {path: rasterio.open(path) for path, _ in overview_index}
    try:
        for z in range(MIN_ZOOM, OVERVIEW_MAX_ZOOM + 1):
            for x, y in tiles_intersecting_geom(corridor_merc, z):
                merc_bounds = tile_bounds_merc(z, x, y)
                matching = [path for path, bounds in overview_index if bounds_intersect(bounds, merc_bounds)]
                if not matching:
                    continue
                res = (merc_bounds[2] - merc_bounds[0]) / TILE_PX
                arr, _ = merge(
                    [srcs[p] for p in matching],
                    bounds=merc_bounds,
                    res=(res, res),
                    resampling=Resampling.average,
                    indexes=[1, 2, 3],
                )
                if not arr.any():
                    continue
                tiles[(z, x, y)] = encode_webp(arr)
                for path in matching:
                    contributions[(z, path)] = contributions.get((z, path), 0) + 1
    finally:
        for src in srcs.values():
            src.close()
    return tiles, contributions


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


def assemble(cells_dir: Path, cells_json: Path, corridor_path: Path, centerline_path: Path, out_dir: Path):
    corridor_merc = load_geom_merc(corridor_path)
    band_merc = load_geom_merc(centerline_path).buffer(BAND_METERS)
    corridor_4326 = json.loads(corridor_path.read_text())
    from shapely.geometry import shape
    from shapely.ops import unary_union

    geoms = (
        [shape(f["geometry"]) for f in corridor_4326["features"]]
        if corridor_4326.get("type") == "FeatureCollection"
        else [shape(corridor_4326.get("geometry", corridor_4326))]
    )
    header_bounds = unary_union(geoms).bounds

    receipts = load_receipts(cells_json, cells_dir)
    verify_receipts(receipts, corridor_merc, band_merc, cells_dir)
    print(f"{len(receipts)} receipts verified; ownership tiles the corridor exactly.")

    overview_index = index_overviews(cells_dir)
    if len(overview_index) != len(receipts):
        raise SystemExit(
            f"{len(overview_index)} overviews for {len(receipts)} cells - a lost overview would leave a hole in every low zoom."
        )

    print("Rendering low zooms from overviews...")
    low_tiles, contributions = render_low_zoom_tiles(corridor_merc, overview_index)
    print(f"{len(low_tiles)} low-zoom tiles rendered.")

    # The same completeness gate export_pmtiles.py held, per overview per
    # zoom - by bounds attribution, since merge() does not report which
    # source painted which pixel.
    counts = {
        f"zoom {z}: {path.name}": contributions.get((z, path), 0)
        for z in range(MIN_ZOOM, OVERVIEW_MAX_ZOOM + 1)
        for path, _ in overview_index
    }
    fail_if_incomplete(count_problems(counts), label="Incomplete low-zoom coverage")

    out_dir.mkdir(parents=True, exist_ok=True)
    low_sorted = sorted(low_tiles.items(), key=lambda item: zxy_to_tileid(*item[0]))
    for name, tier_max in TIERS:
        out_path = out_dir / name
        written = 0
        with write(str(out_path)) as writer:
            for (z, x, y), data in low_sorted:
                writer.write_tile(zxy_to_tileid(z, x, y), data)
                written += 1
            for (z, x, y), data in native_tile_stream(receipts, cells_dir, tier_max):
                writer.write_tile(zxy_to_tileid(z, x, y), data)
                written += 1
            writer.finalize(
                build_header(header_bounds),
                {"name": f"OurHike background z{tier_max}", "format": "webp"},
            )
        print(f"{name}: {written} tiles, {out_path.stat().st_size / 1e6:.1f} MB")


def main(args: argparse.Namespace):
    assemble(args.cells_dir, args.cells_json, args.corridor, args.centerline, args.out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cells-dir", type=Path, default=DEFAULT_CELLS_DIR)
    parser.add_argument("--cells-json", type=Path, default=DEFAULT_CELLS_JSON)
    parser.add_argument("--corridor", type=Path, default=DEFAULT_CORRIDOR)
    parser.add_argument("--centerline", type=Path, default=DEFAULT_CENTERLINE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    main(parser.parse_args())
