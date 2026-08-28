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

THE CORRIDOR NARROWS WITH DEPTH (#1088). Its own shape since then, rather
than the basemap's: 30 miles through z11, 15 at z12, 6 at z13, because a
mile of buffer costs 1.36 MB at z11 and 12.37 MB at z13. See
CORRIDOR_TAPER_MILES for the measurement and for why terrain does not want
the 30 miles the POI corridor is argued to. The schedule is written into the
archive's metadata, so check_dem_archive.py holds a build to the shape it
declares rather than to whatever this constant says at gate time.
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
from shapely.geometry import box

from export_basemap import load_corridor_4326, report_archive
from extract_package import load_region, tiles_intersecting, to_mercator
from lib.http_retry import request_with_retry

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"
# The canonical variant's output. Kept as a module constant because
# check_dem_archive.py imports it as its own default archive.
OUT_PATH = PROCESSED_DIR / "dem.pmtiles"

# The same bucket, path and encoding the client streams from live
# (client/src/map/terrain.ts DEM_TILE_URL) - this stage repackages the data
# the app already trusts rather than introducing a second elevation source.
DEM_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

MIN_ZOOM = 0
# See module docstring - the 10 m source saturates ~z14, and the client
# already overzooms its DEM (terrain.ts DEM_MAX_ZOOM=13, contours to 15).
MAX_ZOOM = 13

QUANTIZE_STEP_M = 0.5

# How wide the terrain corridor is AT EACH ZOOM - the taper (#1088). Read as
# "from this zoom until the next entry": z0-11 at 30 miles, z12 at 15, z13 at 6.
#
# WHY THIS IS NOT ONE NUMBER. A mile of extra buffer does not cost the same at
# every zoom, because tile count quadruples per level while tile width halves.
# Measured 2026-08-27 against the real ANST centerline (3,025 features from
# ATC's ArcGIS service, buffered in EPSG:5070, counted with
# extract_package.tiles_intersecting - the method reproduces the published
# 15,932 z13 tiles to 0.12%), priced at the published per-zoom mean bytes/tile:
#
#     zoom | tile width | MB per mile of buffer
#     z11  |    9.31 mi |  1.36
#     z12  |    4.66 mi |  4.12
#     z13  |    2.33 mi | 12.37
#
# Width is ~9x more expensive at z13 than at z11. A uniform buffer therefore
# spends nearly all its bytes buying width at exactly the zoom a hiker uses to
# look at the ground under their feet, and nearly none at the zoom they pan out
# to. Tapering buys width where it is cheap.
#
# WHY IT IS NOT THE BASEMAP'S 30. Until #1088 this exporter took its shape from
# export_basemap.load_corridor_4326(), i.e. lib/corridor.BUFFER_MILES. That 30
# is argued in corridor.py from POI context - "towns, resupply, parking, the
# things a thru-hiker leaves the trail for" - which is a reason to keep the
# BASEMAP wide (the road a hiker bails out on) and not a reason to carry
# hillshade and contours 25 miles off-trail. Nobody bails out by reading relief
# shading.
#
# The shallow zooms are deliberately absent from the taper: z0-9 escape the
# corridor entirely (see CONTEXT_ZOOM below) and z10-11 inherit the widest
# entry, because a z10 tile is 18.6 miles wide and a narrower buffer barely
# changes which tiles are kept. Pan-out context stays whole either way.
#
# BUILT AND MEASURED at this schedule (2026-08-27, run 33065213666): 8,658
# tiles, 275.6 MB, against the untapered 607.3 - 54.6% off the DEM and 42.0%
# off the Standard hiking sheet. Per band: z0-9 29.4, z10 11.8, z11 49.3,
# z12 78.8, z13 106.2.
#
# @unvalidated AS NUMBERS. 30/15/6 is the maintainer's opening schedule
# (2026-08-27), not a finding - the SHAPE is measured and the SIZE is now
# measured, but the three values are still picked. 6 is 2x
# trailPosition.MAX_OFF_TRAIL_MILES, the distance past which the app already
# declines to say where a hiker is, though note that constant is itself derived
# from bucket-search geometry rather than from how far hikers actually wander. What would settle it: what a hiker pans to when they are
# lost and off-trail, which nothing in this project measures yet.
#
# WHAT THIS DOES TO THE BUILDS ALREADY IN THE FIELD, weighed and accepted by the
# maintainer 2026-08-28 rather than left for somebody to find. `dem.pmtiles` is
# a flat root key, so tapering it REPLACED the bytes behind a name every
# deployed build asks for - v1.0.0, v1.1.0 and v1.1.1 alike - and those builds
# have no ancestor-tile fallback: `demTiles.ts` at each of those tags THROWS on
# an archive miss, where the current client upscales the nearest ancestor it
# holds. So a hiker on a shipped build who RE-DOWNLOADS terrain gets blank
# hillshade offline past 6 miles from the trail at z13 (15 at z12), where their
# previous download drew relief.
#
# Accepted because the exposure is narrow and the failure is quiet rather than
# dangerous: an archive already on a phone is untouched (no bucket policy
# reaches it), a mid-flight download detects the republish by its published hash
# and restarts clean rather than splicing, the affected ground is past
# MAX_OFF_TRAIL_MILES where the app already declines to say where somebody is,
# and blank terrain is a missing texture rather than a wrong one - the trail,
# the waypoints and the position all still draw. What it costs is a hiker who
# deletes and re-downloads at a resupply stop, which is a real thing people do.
# The window closes when the current client ships.
CORRIDOR_TAPER_MILES = {0: 30.0, 12: 15.0, 13: 6.0}

# The hiking sheet's LIGHT level: the same archive shape at a harder taper
# (#1088). Its own artifact rather than a cut the client performs, for the
# reason publish.py's basemap_z13 is one - "a download must be exactly the
# bytes its advertised size and published hash describe".
#
# WHAT LIGHT TRADES, said plainly, because it is not the trade Standard makes.
# Standard already narrows: 6 miles of z13 either side of the trail. Light
# halves that to 3 - which is exactly trailPosition.MAX_OFF_TRAIL_MILES, the
# distance past which the app already refuses to say where a hiker is - and
# pulls z12 in to 6 miles and the shallow corridor to 20. So terrain runs out
# closer to the trail at every zoom, and a hiker who wanders further than the
# app can locate them has no hillshade where they are. That is the honest
# summary of the rung, and the reason it is not the default.
#
# @unvalidated AS NUMBERS, more so than Standard's. 20/6/3 is picked to sit a
# meaningful distance below Standard while keeping z13 out to the locating
# limit; nothing has measured what a hiker on the Light rung actually loses.
# What would settle it is the same thing Standard's taper waits on: where
# people pan when they are lost.
LIGHT_TAPER_MILES = {0: 20.0, 12: 6.0, 13: 3.0}

# The variants this exporter knows how to build, as (output filename, taper).
# The names are publish.py's OFFLINE_SHEET_ARCHIVES spellings, which are the
# flat R2 keys the client requests - so a variant added here and not there
# builds an archive nothing publishes, and one added there and not here names
# an artifact nothing produces. test_export_dem.py pins the pair.
VARIANTS = {
    "canonical": ("dem.pmtiles", CORRIDOR_TAPER_MILES),
    "light": ("dem_light.pmtiles", LIGHT_TAPER_MILES),
}

# Below and including this zoom the corridor is not applied at all: the archive
# keeps every tile in the corridor's BOUNDING BOX, so panning out offline shows
# terrain instead of a 60-mile ribbon floating in blank paper.
#
# THE SAME BOUNDARY extract_package.DEFAULT_CONTEXT_ZOOM and
# cut_stretches.STRETCH_CONTEXT_ZOOM already draw, and it was a real gap that
# the DEM did not draw it too: the vector sheet has kept its whole footprint
# through z9 since #189 ("panning out offline shows the ground around the trail
# instead of blank paper"), while the hillshade under it stopped at the
# corridor. Panned out with no signal those two disagreed on screen, and the
# disagreement was a packaging artefact rather than a fact about the ground.
#
# CHEAP, MEASURED, AND ONLY JUST. Corridor tiles against bounding-box tiles at
# each zoom, and what unclipping costs cumulatively (2026-08-27, real ANST
# centerline, priced at the published per-zoom mean bytes/tile):
#
#     zoom | corridor | bbox | ratio | cumulative cost of unclipping
#     z9   |      107 |  576 |  5.4x |  +26.5 MB
#     z10  |      329 | 2256 |  6.9x | +106.5 MB
#     z11  |    1,139 | 8740 |  7.7x | +435.5 MB
#
# So z9 is where it stops being cheap, which is why the constant the project
# already had is also the right one here rather than a coincidence. Raising
# this to 11 would spend more on terrain nobody navigates by than the whole
# taper below saves.
CONTEXT_ZOOM = 9

FETCH_WORKERS = 16
# The pause ladder between retries of one tile - lib/http_retry's mechanism,
# shorter than its default because a 20k-tile run cannot afford a 30s pause
# per flake against a bucket this reliable. The old loop here retried with
# NO sleep at all (#659), which against a briefly-overloaded server is three
# instant hits and a dead run.
FETCH_BACKOFF_SECONDS = (2, 10)


def parse_taper(spec: str) -> dict[int, float]:
    """A taper from the command line: "0:30,12:15,13:6" - zoom:miles pairs.

    Validated rather than trusted, because a typo here silently ships a map
    with a hole in it: every zoom must be a non-negative int, every width
    positive, and a 0 entry is required so taper_miles() is total (see there).
    """
    taper: dict[int, float] = {}
    for pair in spec.split(","):
        zoom, _, miles = pair.strip().partition(":")
        if not _:
            raise ValueError(f"taper entry {pair!r} is not zoom:miles")
        z, m = int(zoom), float(miles)
        if z < 0:
            raise ValueError(f"taper zoom {z} is negative")
        if m <= 0:
            raise ValueError(f"taper width {m} at zoom {z} must be positive")
        taper[z] = m
    if 0 not in taper:
        raise ValueError(f"taper {spec!r} needs a 0 entry, so every zoom has a width")
    return taper


def taper_miles(zoom: int, taper: dict[int, float] = CORRIDOR_TAPER_MILES) -> float:
    """How wide the corridor is at `zoom`, per the taper's step-function
    reading: the entry for the deepest breakpoint at or above which `zoom`
    sits. A zoom below every breakpoint takes the shallowest entry, which is
    why CORRIDOR_TAPER_MILES carries a 0 key - so this is total over the
    zooms, never a KeyError on a shallow one."""
    applicable = [z for z in taper if z <= zoom]
    if not applicable:
        raise ValueError(f"taper {sorted(taper)} has no entry at or below zoom {zoom}; it needs a 0 key")
    return taper[max(applicable)]


def tapered_tiles(
    min_zoom: int,
    max_zoom: int,
    taper: dict[int, float] = CORRIDOR_TAPER_MILES,
    region=None,
    context_zoom: int = CONTEXT_ZOOM,
) -> tuple[list[tuple[int, int, int]], object]:
    """Every (z, x, y) the tapered corridor keeps, plus the WIDEST region -
    which is what the archive header's bounds must describe, since the header
    carries one bbox for an archive whose shape now narrows with depth.

    Zooms are grouped by the width they ask for, and each group walks its own
    region. One `tiles_intersecting` call per DISTINCT width rather than per
    zoom: the call descends a quadtree from min_zoom, so asking it for the
    whole range and keeping one group's zooms is correct (a narrow region's
    hits are a subset of a wide one's at every level) and costs one descent
    per width instead of one per zoom.

    `region` overrides the corridor entirely - a hand-drawn shape used at every
    zoom, i.e. no taper. That is what --region has always meant and it keeps
    meaning it.
    """
    zooms = range(min_zoom, max_zoom + 1)
    if region is not None:
        hits = tiles_intersecting(to_mercator(region), min_zoom, max_zoom)
        return [(z, x, y) for z in zooms for x, y in hits[z]], region

    widths: dict[float, list[int]] = {}
    context_zooms = []
    for z in zooms:
        if z <= context_zoom:
            context_zooms.append(z)
        else:
            widths.setdefault(taper_miles(z, taper), []).append(z)

    tiles: list[tuple[int, int, int]] = []
    widest_region = None
    for miles in sorted(widths, reverse=True):
        print(f"  building corridor at {miles} miles for zoom {widths[miles]}...")
        shape = load_corridor_4326(buffer_miles=miles)
        if widest_region is None:
            widest_region = shape
        hits = tiles_intersecting(to_mercator(shape), min_zoom, max_zoom)
        tiles += [(z, x, y) for z in widths[miles] for x, y in hits[z]]

    if context_zooms:
        # The widest corridor's BOUNDING BOX, not the corridor - see
        # CONTEXT_ZOOM. Built from the widest entry so the box does not shrink
        # when the taper's deep end is tightened; the context a hiker pans out
        # to should not move because somebody re-tuned z13.
        widest = widest_region if widest_region is not None else load_corridor_4326(buffer_miles=taper_miles(0, taper))
        context = box(*widest.bounds)
        print(f"  keeping the full bounding box for zoom {context_zooms} (context)")
        hits = tiles_intersecting(to_mercator(context), min_zoom, max_zoom)
        tiles += [(z, x, y) for z in context_zooms for x, y in hits[z]]
        if widest_region is None:
            widest_region = widest

    # Sorted so the writer still sees (z, x, y) walk order across groups - the
    # clustering main() relies on to avoid a post-pass.
    return sorted(tiles), widest_region


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
    transient faults and 429/5xx over FETCH_BACKOFF_SECONDS via
    lib/http_retry (#659 - the hand-rolled loop here slept zero seconds
    between attempts, and retried even statuses that are answers). A 404 is
    not a fault: the dataset is global, so absence is unexpected but not
    worth failing a 20k-tile run over - absences are counted and reported
    by main()."""
    url = DEM_TILE_URL.format(z=z, x=x, y=y)
    try:
        resp = request_with_retry(url, session=session, backoff=FETCH_BACKOFF_SECONDS, label=f"tile {z}/{x}/{y}")
    except requests.exceptions.HTTPError as error:
        if error.response is not None and error.response.status_code == 404:
            return None
        raise
    return resp.content


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

    # --variant names a shape; --out and --taper override it, so a spike can
    # still build anything without inventing a variant for it.
    variant_out, variant_taper = VARIANTS[args.variant]
    taper = parse_taper(args.taper) if args.taper else variant_taper
    out = args.out if args.out is not None else PROCESSED_DIR / variant_out
    region = load_region(args.region) if args.region else None

    if region is None:
        print(f"Building tapered corridor, zoom {args.min_zoom}-{args.max_zoom}...")
        print(f"  taper: {', '.join(f'z{z}+ = {m} mi' for z, m in sorted(taper.items()))}")
    else:
        print(f"Walking region tiles, zoom {args.min_zoom}-{args.max_zoom} (--region overrides the taper)...")

    tiles, region = tapered_tiles(args.min_zoom, args.max_zoom, taper, region)
    if args.limit and len(tiles) > args.limit:
        raise SystemExit(
            f"{len(tiles)} tiles exceed --limit {args.limit}. The limit exists so a mis-drawn "
            "region fails before fetching the world - raise it deliberately, not reflexively."
        )
    print(f"{len(tiles)} tiles to fetch (quantize step {args.quantize_step} m, {args.workers} workers)")

    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    absent: list[list[int]] = []
    session = requests.Session()

    def process(zxy: tuple[int, int, int]) -> bytes | None:
        png = fetch_tile(session, *zxy)
        return None if png is None else encode_tile(png, unit)

    with write(str(out)) as writer:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            # executor.map preserves submission order, so tiles are written in
            # the sorted (z, x, y) walk order - keeping the archive clustered
            # without a post-pass.
            for (z, x, y), data in zip(tiles, pool.map(process, tiles)):
                if data is None:
                    absent.append([z, x, y])
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
                # The shape this archive was actually built to, for the same
                # reason absent_tiles is written below: check_dem_archive.py
                # must be able to tell "a tile the taper excluded" from "a
                # tile lost in transit", and it cannot do that against a
                # constant that may have moved since the build ran. Null for
                # a --region build, which has no taper - one shape, every zoom.
                "corridor_taper_miles": (None if args.region else {str(z): m for z, m in sorted(taper.items())}),
                # WHICH tiles the source had no answer for, not just how
                # many (#659): check_dem_archive.py excuses exactly these
                # and no others, so an upstream absence this run tolerated
                # stays distinguishable from a tile lost in transit.
                "absent_tiles": sorted(absent),
            },
        )

    print(f"{written} tiles written, {len(absent)} absent from source")
    report_archive(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", type=Path, default=None, help="GeoJSON region (default: build the AT corridor)")
    parser.add_argument("--out", type=Path, default=None, help="Output .pmtiles path (default: the variant's)")
    parser.add_argument(
        "--variant",
        choices=sorted(VARIANTS),
        default="canonical",
        help="Which published shape to build; --out and --taper override it",
    )
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM, help=f"Default {MAX_ZOOM}; see module docstring before raising")
    parser.add_argument("--quantize-step", type=float, default=QUANTIZE_STEP_M, help="Vertical floor in meters (1.0, 0.5, 0.25)")
    parser.add_argument(
        "--taper",
        default=None,
        help='Corridor width per zoom, "zoom:miles" pairs (default '
        f'"{",".join(f"{z}:{m:g}" for z, m in sorted(CORRIDOR_TAPER_MILES.items()))}"). Ignored with --region.',
    )
    parser.add_argument("--workers", type=int, default=FETCH_WORKERS)
    parser.add_argument("--limit", type=int, default=0, help="Refuse to fetch more than this many tiles (0 = no limit)")
    parser.add_argument("--name", default="OurHike DEM", help="Metadata name for the archive")
    main(parser.parse_args())
