"""Cut a trail-shaped download package out of a bigger PMTiles archive - the
"extract many" half of the build-once-extract-many design in BASEMAP.md
(issues #184/#185).

export_basemap.py builds one archive per refresh; this cuts what one trail's
hikers actually download. The two are separate scripts because they scale
differently: the build is the periodic heavy job, extraction is minutes per
trail against a local file - so adding a trail costs one run of this script,
never another build.

Implemented over the pmtiles package this pipeline already depends on rather
than the go-pmtiles CLI: no external binary to install or pin, and the
region-intersection walk reuses lib/tiling.py exactly the way
export_pmtiles.py's raster tiling does. go-pmtiles remains the right tool for
extracting from a REMOTE archive (it does clustered range requests); this
operates on the build output sitting beside it on disk, where plain reads
win on simplicity. Tile bytes are copied verbatim - Reader.get returns
stored bytes without decompressing, so the package carries the source's
tile_compression unchanged and never re-encodes anything.

The region walk descends the tile quadtree - a tile's children can only
intersect the region if the tile does - so the corridor's huge bounding box
never turns into millions of point tests at z14.
"""

import argparse
import json
from pathlib import Path

from pmtiles.reader import Reader, all_tiles
from pmtiles.tile import deserialize_header, zxy_to_tileid
from pmtiles.writer import write
from pyproj import Transformer
from shapely.geometry import box, shape
from shapely.ops import transform
from shapely.prepared import prep

from export_basemap import report_archive
from lib.tiling import tile_bounds_merc, tile_range_for_bounds

MERC_CRS = "EPSG:3857"
GEOGRAPHIC_CRS = "EPSG:4326"


def load_region(path: Path):
    """The region as one shapely geometry in EPSG:4326. Accepts a bare
    Geometry, a Feature, or a FeatureCollection (unioned), so the same flag
    takes export_basemap.py's basemap_region.geojson or any hand-drawn
    trail-corridor file."""
    parsed = json.loads(path.read_text())
    if parsed.get("type") == "FeatureCollection":
        geoms = [shape(feature["geometry"]) for feature in parsed["features"]]
        region = geoms[0]
        for geom in geoms[1:]:
            region = region.union(geom)
        return region
    if parsed.get("type") == "Feature":
        return shape(parsed["geometry"])
    return shape(parsed)


def to_mercator(region_4326):
    """always_xy for the same reason lib/corridor.py documents: every geometry
    in this pipeline is (lon, lat), and pyproj's authority-order default would
    silently swap axes."""
    transformer = Transformer.from_crs(GEOGRAPHIC_CRS, MERC_CRS, always_xy=True)
    return transform(transformer.transform, region_4326)


def tiles_intersecting(region_merc, min_zoom: int, max_zoom: int) -> dict[int, list[tuple[int, int]]]:
    """Per-zoom (x, y) lists of tiles whose bounds intersect the region.

    Quadtree descent: the candidates at z+1 are only the children of hits at
    z. Correct because a child's bounds lie inside its parent's, so a tile
    whose parent misses the region cannot itself intersect it."""
    prepared = prep(region_merc)
    x0, x1, y0, y1 = tile_range_for_bounds(region_merc.bounds, min_zoom)
    hits: dict[int, list[tuple[int, int]]] = {
        min_zoom: [
            (x, y)
            for x in range(x0, x1 + 1)
            for y in range(y0, y1 + 1)
            if prepared.intersects(box(*tile_bounds_merc(min_zoom, x, y)))
        ]
    }
    for z in range(min_zoom + 1, max_zoom + 1):
        hits[z] = [
            (cx, cy)
            for x, y in hits[z - 1]
            for cx in (2 * x, 2 * x + 1)
            for cy in (2 * y, 2 * y + 1)
            if prepared.intersects(box(*tile_bounds_merc(z, cx, cy)))
        ]
    return hits


def package_header(source_header: dict, region_4326, min_zoom: int) -> dict:
    """The package's header: the source's format facts (tile type and
    compression - the bytes are copied verbatim, so these MUST carry over),
    the region's own bounds rather than the source's, and the same
    center-on-min-zoom convention export_pmtiles.py uses."""
    min_lon, min_lat, max_lon, max_lat = region_4326.bounds
    return {
        "tile_type": source_header["tile_type"],
        "tile_compression": source_header["tile_compression"],
        "min_lon_e7": int(min_lon * 1e7),
        "min_lat_e7": int(min_lat * 1e7),
        "max_lon_e7": int(max_lon * 1e7),
        "max_lat_e7": int(max_lat * 1e7),
        "center_lon_e7": int((min_lon + max_lon) / 2 * 1e7),
        "center_lat_e7": int((min_lat + max_lat) / 2 * 1e7),
        "center_zoom": min_zoom,
    }


def extract(source_path: Path, region_path: Path, out_path: Path, min_zoom: int | None, max_zoom: int | None, name: str):
    region = load_region(region_path)
    region_merc = to_mercator(region)

    with open(source_path, "rb") as f:

        def get_bytes(offset, length):
            f.seek(offset)
            return f.read(length)

        source_header = deserialize_header(get_bytes(0, 127))
        reader = Reader(get_bytes)
        metadata = reader.metadata()

        lo = source_header["min_zoom"] if min_zoom is None else min_zoom
        hi = source_header["max_zoom"] if max_zoom is None else max_zoom

        print(f"Walking region tiles, zoom {lo}-{hi}...")
        hits = tiles_intersecting(region_merc, lo, hi)
        wanted = {(z, x, y) for z, tiles in hits.items() for x, y in tiles}

        # One streaming pass over the source rather than one Reader.get() per
        # wanted tile: get() re-reads and re-parses the directory tree on
        # every call, which at package scale (~10^5 tiles) turns minutes into
        # hours. all_tiles() walks each directory exactly once, in tile-id
        # order - which also keeps the output clustered for free.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with write(str(out_path)) as writer:
            for (z, x, y), data in all_tiles(get_bytes):
                if (z, x, y) in wanted:
                    writer.write_tile(zxy_to_tileid(z, x, y), data)
                    written += 1
            if written == 0:
                raise SystemExit("Region intersects no tiles in the source archive - wrong region file, or wrong source?")
            writer.finalize(package_header(source_header, region, lo), {**metadata, "name": name})

    # A region tile absent from the source is normal, not an error: the
    # source was itself clipped (ocean, sparse low zooms), and PMTiles has no
    # empty-tile entries - so absence is reported, never failed on.
    print(f"{written} tiles written, {len(wanted) - written} region tiles absent from source")
    print(f"Source: {source_path.stat().st_size / 1e6:.1f} MB -> package: {out_path.stat().st_size / 1e6:.1f} MB")


def main(args: argparse.Namespace):
    extract(args.source, args.region, args.out, args.min_zoom, args.max_zoom, args.name)
    report_archive(args.out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="The built archive to cut from (export_basemap.py's output)")
    parser.add_argument("--region", type=Path, required=True, help="GeoJSON polygon to cut (e.g. basemap_region.geojson)")
    parser.add_argument("--out", type=Path, required=True, help="Output package .pmtiles path")
    parser.add_argument("--min-zoom", type=int, default=None, help="Default: the source archive's own min zoom")
    parser.add_argument("--max-zoom", type=int, default=None, help="Default: the source archive's own max zoom")
    parser.add_argument("--name", default="OurHike basemap package", help="Metadata name for the package")
    main(parser.parse_args())
