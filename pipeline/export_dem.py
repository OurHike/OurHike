"""Package a region's elevation model as an offline PMTiles archive - the
terrain half of the offline map program (issues #184/#186/#198).

The client's live topographic sheet derives BOTH its hillshade and its
contour lines from one DEM: terrarium-encoded PNG tiles streamed from the
AWS Open Data bucket (client/src/map/terrain.ts). Offline, that stream has
to become an archive on the phone. This stage fetches the same tiles from
the same bucket - the data the app already trusts and credits - and
repackages them smaller:

  quantize    terrarium encodes elevation as (R*256 + G + B/256) - 32768,
              so the blue channel is sub-meter fraction. Over the AT the
              source is ~10 m 3DEP with vertical error well above half a
              meter, so that fraction is noise carried at full entropy.
              Flooring blue to a step (1 m default) discards nothing real.
  re-encode   lossless WebP instead of PNG. Same pixels, smaller bytes;
              MapLibre's raster-dem and maplibre-contour both decode via
              the browser's image decoder, which speaks WebP.

Measured at full scale (build-dem.yml run 1, 2026-08-05): the z0-13 corridor
archive at 1 m quantization is 397.6 MB where stock PNG packaging would be
~2.45 GB - 6.2x smaller.

The quantization step defaults to 0.5 m, decided from evidence rather than
caution (#186's banding check, 2026-08-06, spike_dem_banding.py): at 1 m,
hillshade rendered from the tiles at their native z12-13 shows only diffuse
sub-threshold speckle, but the client OVERZOOMS this DEM - terrain.ts caps
it at z13 and displays it to z15 - and under 4x bilinear magnification the
1 m staircase etches visibly across exactly the gentle valley floors the AT
crosses (Cumberland Valley PA, Harlem Valley NY: 7.6% of hillshade pixels
shifted >8/255). At 0.5 m the overzoomed render is indistinguishable from
unquantized, at ~1.6x the bytes of 1 m.

Quantization is FLOOR, not round: rounding blue up can carry past 255 into
the green channel, and a carry bug here is a silently wrong elevation. A
floor is carry-free by construction and biases at most one step downward,
which the contour intervals in use (20 ft and coarser) cannot see.

Region- and zoom-parameterized like the rest of the basemap tooling
(BASEMAP.md): the AT corridor is the default, not an assumption. Max zoom
defaults to 13 - the 10 m source saturates around z14 (256px tiles), so
deeper levels would quadruple bytes for no information.
"""

import argparse
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write

from export_basemap import load_corridor_4326, report_archive
from extract_package import load_region, tiles_intersecting, to_mercator

ROOT = Path(__file__).parent
OUT_PATH = ROOT / "data" / "processed" / "dem.pmtiles"

# The same bucket, path and encoding the client streams from live
# (client/src/map/terrain.ts DEM_TILE_URL) - this stage repackages the data
# the app already trusts rather than introducing a second elevation source.
DEM_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

MIN_ZOOM = 0
# See module docstring - the 10 m source saturates ~z14, and the client
# already overzooms its DEM (terrain.ts DEM_MAX_ZOOM=13, contours to 15).
MAX_ZOOM = 13

QUANTIZE_STEP_M = 0.5
FETCH_WORKERS = 16
FETCH_ATTEMPTS = 3


def quantize_unit(step_m: float) -> int:
    """The blue-channel floor unit for a vertical step in meters.

    Blue counts 1/256ths of a meter, so a step of s meters is 256*s blue
    units. Constrained to units that divide 256 evenly (1.0, 0.5, 0.25...):
    any other step would need cross-channel arithmetic, reintroducing
    exactly the carry risk the floor design exists to rule out."""
    unit = round(step_m * 256)
    if not (0 < unit <= 256 and 256 % unit == 0):
        raise ValueError(f"quantize step must be 256/2^n meters (1.0, 0.5, 0.25...), got {step_m}")
    return unit


def floor_blue(rgb: np.ndarray, unit: int) -> np.ndarray:
    """Floor the blue channel to `unit`, in place, and return the array.

    Only blue is touched - red and green carry whole meters and pass through
    bit-exact, which is what keeps this step's error bound provable. Shared
    with spike_dem_banding.py so the spike measures the exact transform this
    exporter ships, not a reimplementation of it."""
    if unit >= 256:
        rgb[:, :, 2] = 0
    else:
        rgb[:, :, 2] = (rgb[:, :, 2] // unit) * unit
    return rgb


def encode_tile(png_bytes: bytes, unit: int) -> bytes:
    """One tile: decode terrarium PNG, floor blue to `unit`, lossless WebP."""
    rgb = floor_blue(np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGB")).copy(), unit)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def fetch_tile(session: requests.Session, z: int, x: int, y: int) -> bytes | None:
    """One tile's PNG bytes, or None where the bucket has no tile. Retries
    transient failures; a 404 is not one - the dataset is global, so absence
    is unexpected but not worth failing a 20k-tile run over. Absences are
    counted and reported by main()."""
    url = DEM_TILE_URL.format(z=z, x=x, y=y)
    last_error: Exception | None = None
    for _ in range(FETCH_ATTEMPTS):
        try:
            resp = session.get(url, timeout=60)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as error:
            last_error = error
    raise RuntimeError(f"failed to fetch {url} after {FETCH_ATTEMPTS} attempts") from last_error


def build_header(region_4326, min_zoom: int) -> dict:
    min_lon, min_lat, max_lon, max_lat = region_4326.bounds
    return {
        "tile_type": TileType.WEBP,
        "tile_compression": Compression.NONE,
        "min_lon_e7": int(min_lon * 1e7),
        "min_lat_e7": int(min_lat * 1e7),
        "max_lon_e7": int(max_lon * 1e7),
        "max_lat_e7": int(max_lat * 1e7),
        "center_lon_e7": int((min_lon + max_lon) / 2 * 1e7),
        "center_lat_e7": int((min_lat + max_lat) / 2 * 1e7),
        "center_zoom": min_zoom,
    }


def main(args: argparse.Namespace):
    unit = quantize_unit(args.quantize_step)

    if args.region is None:
        print("Building corridor from centerline...")
        region = load_corridor_4326()
    else:
        region = load_region(args.region)

    print(f"Walking region tiles, zoom {args.min_zoom}-{args.max_zoom}...")
    hits = tiles_intersecting(to_mercator(region), args.min_zoom, args.max_zoom)
    tiles = [(z, x, y) for z in range(args.min_zoom, args.max_zoom + 1) for x, y in hits[z]]
    if args.limit and len(tiles) > args.limit:
        raise SystemExit(
            f"{len(tiles)} tiles exceed --limit {args.limit}. The limit exists so a mis-drawn "
            "region fails before fetching the world - raise it deliberately, not reflexively."
        )
    print(f"{len(tiles)} tiles to fetch (quantize step {args.quantize_step} m, {args.workers} workers)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = absent = 0
    session = requests.Session()

    def process(zxy: tuple[int, int, int]) -> bytes | None:
        png = fetch_tile(session, *zxy)
        return None if png is None else encode_tile(png, unit)

    with write(str(args.out)) as writer:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            # executor.map preserves submission order, so tiles are written in
            # the sorted (z, x, y) walk order - keeping the archive clustered
            # without a post-pass.
            for (z, x, y), data in zip(tiles, pool.map(process, tiles)):
                if data is None:
                    absent += 1
                    continue
                writer.write_tile(zxy_to_tileid(z, x, y), data)
                written += 1
                if written % 1000 == 0:
                    print(f"  {written}/{len(tiles)} written")
        if written == 0:
            raise SystemExit("No tiles fetched - wrong region, or the tile source is unreachable?")
        writer.finalize(
            build_header(region, args.min_zoom),
            {
                "name": args.name,
                "encoding": "terrarium",
                "quantize_step_m": args.quantize_step,
                "attribution": "Elevation: USGS 3DEP via AWS Terrain Tiles",
            },
        )

    print(f"{written} tiles written, {absent} absent from source")
    report_archive(args.out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", type=Path, default=None, help="GeoJSON region (default: build the AT corridor)")
    parser.add_argument("--out", type=Path, default=OUT_PATH, help=f"Output .pmtiles path (default {OUT_PATH})")
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM, help=f"Default {MAX_ZOOM}; see module docstring before raising")
    parser.add_argument("--quantize-step", type=float, default=QUANTIZE_STEP_M, help="Vertical floor in meters (1.0, 0.5, 0.25)")
    parser.add_argument("--workers", type=int, default=FETCH_WORKERS)
    parser.add_argument("--limit", type=int, default=0, help="Refuse to fetch more than this many tiles (0 = no limit)")
    parser.add_argument("--name", default="OurHike DEM", help="Metadata name for the archive")
    main(parser.parse_args())
