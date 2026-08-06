"""Verify a DEM archive before it is allowed near a hiker's phone - the
publish gate for export_dem.py's output (issue #186).

export_dem.py deliberately tolerates a tile the source bucket lacks: failing
a 20k-tile fetch over one absence would make the build too fragile to run.
That tolerance is right for building and wrong for shipping - a corridor
tile missing from the published archive is a blank hillshade square on a
phone with no signal, found at the worst possible moment. So the leniency
lives in the exporter and the strictness lives here, at the moment an
archive is about to become the thing hikers download:

  coverage    every tile the region walk names, at every zoom, is present.
              The walk is the same tiles_intersecting() the exporter used,
              so the check answers "did the build get everything it tried
              for", not "does this archive resemble a corridor".
  decodes     every tile parses as a 256x256 WebP - the browser's image
              decoder is the only decoder the client has, so bytes PIL
              rejects are bytes MapLibre would render as a hole.
  header      zoom range, tile type and compression match what the client
              assumes (raster-dem over uncompressed WebP, see export_dem.py's
              build_header) - a wrong header renders as no terrain at all.
  metadata    the terrarium encoding and quantize step travel with the
              archive, so a future reader can tell what it is holding.

Region- and zoom-parameterized exactly like export_dem.py; the AT corridor
is the default, not an assumption.
"""

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image
from pmtiles.reader import Reader, all_tiles
from pmtiles.tile import Compression, TileType, deserialize_header

from export_basemap import load_corridor_4326
from export_dem import MAX_ZOOM, MIN_ZOOM, OUT_PATH
from extract_package import load_region, tiles_intersecting, to_mercator

TILE_SIZE = 256


def check_archive(archive: Path, region_4326, min_zoom: int, max_zoom: int) -> list[str]:
    """Every way the archive falls short of shippable, as human sentences.
    An empty list is a pass."""
    problems: list[str] = []

    with open(archive, "rb") as f:

        def get_bytes(offset, length):
            f.seek(offset)
            return f.read(length)

        header = deserialize_header(get_bytes(0, 127))
        if header["min_zoom"] != min_zoom or header["max_zoom"] != max_zoom:
            problems.append(f"header zoom range is {header['min_zoom']}-{header['max_zoom']}, expected {min_zoom}-{max_zoom}")
        if header["tile_type"] != TileType.WEBP:
            problems.append(f"header tile type is {header['tile_type']!r}, expected WebP")
        if header["tile_compression"] != Compression.NONE:
            problems.append(
                f"header tile compression is {header['tile_compression']!r}, expected none - "
                "MapLibre decodes these via the browser's image decoder, which speaks WebP, not gzip"
            )

        print(f"Walking region tiles, zoom {min_zoom}-{max_zoom}...")
        hits = tiles_intersecting(to_mercator(region_4326), min_zoom, max_zoom)
        expected = {(z, x, y) for z, tiles in hits.items() for x, y in tiles}

        held: set[tuple[int, int, int]] = set()
        bad_tiles = 0
        for (z, x, y), data in all_tiles(get_bytes):
            held.add((z, x, y))
            try:
                with Image.open(BytesIO(data)) as image:
                    if image.format != "WEBP" or image.size != (TILE_SIZE, TILE_SIZE):
                        raise ValueError(f"{image.format} {image.size}")
                    image.verify()
            except Exception as error:
                bad_tiles += 1
                if bad_tiles <= 5:
                    problems.append(f"tile {z}/{x}/{y} is not a valid {TILE_SIZE}px WebP: {error}")
        if bad_tiles > 5:
            problems.append(f"...and {bad_tiles - 5} more tiles that do not decode")

        missing = expected - held
        if missing:
            worst = sorted(missing)[:5]
            listed = ", ".join(f"{z}/{x}/{y}" for z, x, y in worst)
            problems.append(
                f"{len(missing)} region tiles missing from the archive (first: {listed}) - "
                "each is a blank terrain square on a phone with no signal"
            )
        # Beyond-region tiles would mean the walk here and the exporter's
        # disagree - not hiker-harming by itself, but proof the check is not
        # checking what was built.
        stray = held - expected
        if stray:
            problems.append(f"{len(stray)} tiles outside the region walk - archive and check disagree about the region")

        metadata = Reader(get_bytes).metadata()
        if metadata.get("encoding") != "terrarium":
            problems.append(f"metadata encoding is {metadata.get('encoding')!r}, expected 'terrarium'")
        if "quantize_step_m" not in metadata:
            problems.append("metadata is missing quantize_step_m - a future reader cannot tell what this holds")

        for z in sorted(hits):
            present = sum(1 for x, y in hits[z] if (z, x, y) in held)
            print(f"  z{z}: {present}/{len(hits[z])} region tiles present")

    return problems


def main(args: argparse.Namespace) -> None:
    if args.region is None:
        print("Building corridor from centerline...")
        region = load_corridor_4326()
    else:
        region = load_region(args.region)

    problems = check_archive(args.archive, region, args.min_zoom, args.max_zoom)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        raise SystemExit(1)
    print(f"PASS: {args.archive} covers the region completely and every tile decodes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", type=Path, default=OUT_PATH, help=f"Archive to check (default {OUT_PATH})")
    parser.add_argument("--region", type=Path, default=None, help="GeoJSON region (default: build the AT corridor)")
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM)
    main(parser.parse_args())
