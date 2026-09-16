"""Is a BAKED hillshade (plus baked contours) smaller than shipping the DEM?

LIGHT_DOWNLOAD.md's "what was rejected" table closes on the one row it could
not close: baking hillshade and contours instead of shipping `dem.pmtiles` is
"not rejected - NOT measured... the largest unmeasured idea here and deserves
its own spike." This is that spike.

WHY IT LOOKS PROMISING ON PAPER. The archive is terrarium-encoded elevation,
and elevation must be carried losslessly because a 1-LSB error in the red
channel is 256 m (LIGHT_DOWNLOAD.md measured 2,771 m RMSE trying otherwise).
A hillshade is a smooth grayscale image with no such cliff, so it tolerates
lossy compression - the one thing terrarium structurally cannot.

WHY IT MIGHT STILL LOSE. The DEM feeds TWO things (liveTopo.ts's hillshade
layer and maplibre-contour's in-browser isolines). Baking only the hillshade
frees nothing: the contours still need elevation, so the DEM ships anyway and
the hillshade is pure addition. To drop the DEM you must bake BOTH, and baked
contours are billed per interval - terrain.ts's CONTOUR_THRESHOLDS changes the
interval at five zooms AND between imperial and metric, which is why that file
rejected baked contours for the live map in the first place.

So the arms are priced as a SWAP, not as a saving in isolation:

    ship today    dem.pmtiles                       (hillshade + contours)
    bake          hillshade raster + contour MVTs   (both units)

METHOD, and what is measured versus reasoned.

  measured  bytes. Every arm is encoded with the real encoder: the DEM arm is
            export_dem.encode_tile itself, so arm A is the shipping transform
            rather than a reimplementation of it. Contours are encoded by
            maplibre-contour's own vtpbf, driven from spike_baked_contours.mjs.
  measured  fidelity. Hillshade rendered with spike_dem_banding's hillshade(),
            compared with its compare() - the same "% of pixels shifted >8/255"
            every prior terrain decision in this repository was made on.
  reasoned  archive projection. Per-zoom BYTE RATIOS from this sample applied
            to the published per-zoom megabytes (LIGHT_DOWNLOAD.md's built
            table). A ratio transfers where a mean bytes/tile does not: both
            arms here are measured over the SAME tiles, so the footprint
            caveat that burned the taper's per-band projection does not apply.

Tile edges are handled the way a real baker would have to: hillshade is a
spatial derivative, so it is computed over a stitched 3x3 block and then cut
to the centre tile. A per-tile bake with no neighbour context seams visibly,
and measuring that instead would be measuring a bug.

Areas are LIGHT_DOWNLOAD.md's six, so the fidelity numbers here sit beside the
z12-cap and 1 m-floor numbers already recorded there rather than beside a new
sample nobody can compare against.

Outputs land in data/spike_baked_terrain/: report.txt, the elevation dumps
spike_baked_contours.mjs reads, and per-area triptychs to look at.
"""

import argparse
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from export_dem import DEM_TILE_URL, encode_tile
from lib.http_retry import request_with_retry
from spike_dem_banding import (
    AZIMUTH_DEG,
    EXAGGERATION,
    GRID,
    TILE_SIZE,
    bilinear_upsample,
    compare,
    elevation,
    hillshade,
    meters_per_pixel,
    tile_xy,
)

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "data" / "spike_baked_terrain"

# LIGHT_DOWNLOAD.md's six, so this sample is comparable with the z12-cap and
# 1 m-floor tables already recorded there. Two valley floors (where
# quantization terraces), four with real relief (where a hillshade has the
# most to say and compresses worst).
AREAS = {
    "cumberland_valley_pa": (40.185, -77.08),
    "harlem_valley_ny": (41.590, -73.590),
    "franconia_ridge_nh": (44.148, -71.644),
    "clingmans_dome_tn": (35.5628, -83.4986),
    "mcafee_knob_va": (37.3917, -80.0367),
    "shenandoah_va": (38.5330, -78.4460),
}

# The zooms the taper actually buys, and the bands that carry the bytes.
# z0-10 is 41.2 MB of the 275.6 and is left alone by every arm here.
ZOOMS = (11, 12, 13)

# Published per-zoom megabytes of the shipped dem.pmtiles, for the projection
# (LIGHT_DOWNLOAD.md, run 33065213666, 2026-08-27). Tile counts are that run's.
PUBLISHED = {11: (1139, 49.3), 12: (2315, 78.8), 13: (4054, 106.2)}
PUBLISHED_SHALLOW_MB = 41.2  # z0-9 29.4 + z10 11.8, untouched by every arm

# WebP qualities to price the baked hillshade at. 75 is PIL's default and the
# middle of the useful range; the sweep exists so the fidelity cliff, if there
# is one, is visible rather than assumed.
QUALITIES = (50, 65, 75, 85, 95)

OVERZOOM = 4  # z13 displayed at z15, the client's cap (map/terrain.ts)


def fetch_block(session: requests.Session, lat: float, lon: float, z: int) -> tuple[np.ndarray, tuple[int, int]]:
    """A stitched GRID x GRID block of raw terrarium RGB, and its centre tile.

    Cached on disk: the bucket's tiles are static, and a spike that re-runs its
    analysis should not re-fetch 162 tiles to do it."""
    cx, cy = tile_xy(lat, lon, z)
    cache = OUT_DIR / f"block_{z}_{cx}_{cy}.npy"
    if cache.exists():
        return np.load(cache), (cx, cy)
    half = GRID // 2
    coords = [(cx + dx, cy + dy) for dy in range(-half, half + 1) for dx in range(-half, half + 1)]

    def one(xy: tuple[int, int]) -> np.ndarray:
        # Through lib/http_retry, the same absorber export_dem.py fetches
        # behind - the sandbox proxy resets often enough that a bare get()
        # loses a 162-tile run to somebody else's transient.
        resp = request_with_retry(
            DEM_TILE_URL.format(z=z, x=xy[0], y=xy[1]),
            session=session,
            label=f"dem z{z}",
        )
        return np.asarray(Image.open(io.BytesIO(resp.content)).convert("RGB"))

    with ThreadPoolExecutor(max_workers=9) as pool:
        tiles = list(pool.map(one, coords))
    rows = [np.concatenate(tiles[r * GRID : (r + 1) * GRID], axis=1) for r in range(GRID)]
    block = np.concatenate(rows, axis=0)
    np.save(cache, block)
    return block, (cx, cy)


def centre(a: np.ndarray) -> np.ndarray:
    """The middle 256px tile of a stitched block."""
    o = (GRID // 2) * TILE_SIZE
    return a[o : o + TILE_SIZE, o : o + TILE_SIZE]


def dem_arm_bytes(rgb_block: np.ndarray) -> int:
    """Arm A: what export_dem.py ships for the centre tile, via its own
    encode_tile - so this is the shipping transform, not a copy of it."""
    buf = io.BytesIO()
    Image.fromarray(centre(rgb_block)).save(buf, format="PNG")
    from export_dem import QUANTIZE_STEP_M, quantize_unit

    return len(encode_tile(buf.getvalue(), quantize_unit(QUANTIZE_STEP_M)))


def webp_gray(img: np.ndarray, quality: int | None) -> bytes:
    """Grayscale WebP, lossless when quality is None."""
    buf = io.BytesIO()
    pil = Image.fromarray(img.astype(np.uint8), mode="L")
    if quality is None:
        pil.save(buf, format="WEBP", lossless=True)
    else:
        pil.save(buf, format="WEBP", quality=quality, lossless=False)
    return buf.getvalue()


def decode_gray(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("L"), dtype=np.uint8)


def main(args: argparse.Namespace) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    report: list[str] = []

    def say(line: str = "") -> None:
        print(line)
        report.append(line)

    say("BAKED TERRAIN SPIKE - is hillshade+contours cheaper than the DEM?")
    say(f"exaggeration {EXAGGERATION}, azimuth {AZIMUTH_DEG}, {GRID}x{GRID} blocks, centre tile measured")
    say()

    # zoom -> arm -> list of per-area bytes / fidelity
    dem_bytes: dict[int, list[int]] = {z: [] for z in ZOOMS}
    bake_bytes: dict[int, dict[object, list[int]]] = {z: {q: [] for q in (None, *QUALITIES)} for z in ZOOMS}
    fidelity: dict[int, dict[object, list[tuple[float, float]]]] = {z: {q: [] for q in QUALITIES} for z in ZOOMS}
    over_bake: dict[int, dict[object, list[tuple[float, float]]]] = {z: {q: [] for q in (None, *QUALITIES)} for z in ZOOMS}
    ship_fid: dict[int, list[tuple[float, float]]] = {z: [] for z in ZOOMS}
    over_ship: dict[int, list[tuple[float, float]]] = {z: [] for z in ZOOMS}
    elev_index: list[dict] = []

    for name, (lat, lon) in AREAS.items():
        for z in ZOOMS:
            block, (cx, cy) = fetch_block(session, lat, lon, z)
            mpp = meters_per_pixel(lat, z)

            elev_raw = elevation(block)
            from export_dem import QUANTIZE_STEP_M, floor_blue, quantize_unit

            elev_ship = elevation(floor_blue(block.copy(), quantize_unit(QUANTIZE_STEP_M)))

            # Reference: hillshade off the block, cut to the centre tile - so
            # every arm is judged on identical ground with identical edges.
            h_ref = centre(hillshade(elev_raw, mpp))
            h_ship = centre(hillshade(elev_ship, mpp))
            ship_fid[z].append(compare(h_ref, h_ship))

            # Overzoom: the regime the app displays (z13 shown to z15).
            up_ref = hillshade(bilinear_upsample(elev_raw, OVERZOOM), mpp / OVERZOOM)
            up_ship = hillshade(bilinear_upsample(elev_ship, OVERZOOM), mpp / OVERZOOM)
            o = (GRID // 2) * TILE_SIZE * OVERZOOM
            s = TILE_SIZE * OVERZOOM
            up_ref_c = up_ref[o : o + s, o : o + s]
            over_ship[z].append(compare(up_ref_c, up_ship[o : o + s, o : o + s]))

            dem_bytes[z].append(dem_arm_bytes(block))
            bake_bytes[z][None].append(len(webp_gray(h_ref, None)))
            # Lossless baked, magnified as an image: isolates the shade-then-
            # magnify difference from anything the codec did.
            over_bake[z][None].append(compare(up_ref_c, bilinear_upsample(h_ref, OVERZOOM).astype(np.uint8)))

            for q in QUALITIES:
                enc = webp_gray(h_ref, q)
                bake_bytes[z][q].append(len(enc))
                dec = decode_gray(enc)
                fidelity[z][q].append(compare(h_ref, dec))
                # A baked tile is magnified as an IMAGE - shade then magnify,
                # where the shipped path magnifies elevation then shades.
                over_bake[z][q].append(compare(up_ref_c, bilinear_upsample(dec, OVERZOOM).astype(np.uint8)))

            # Elevation for the Node contour arm, centre tile plus neighbours.
            stem = f"{name}_z{z}"
            centre(elev_raw).astype(np.float32).tofile(OUT_DIR / f"{stem}_c.f32")
            for i, (dy, dx) in enumerate([(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1)]):
                oy, ox = (dy + 1) * TILE_SIZE, (dx + 1) * TILE_SIZE
                elev_raw[oy : oy + TILE_SIZE, ox : ox + TILE_SIZE].astype(np.float32).tofile(OUT_DIR / f"{stem}_n{i}.f32")
            elev_index.append({"name": name, "z": z, "x": cx, "y": cy, "stem": stem, "lat": lat})

            if args.images:
                trip = np.concatenate([h_ref, h_ship, decode_gray(webp_gray(h_ref, 75))], axis=1)
                Image.fromarray(trip).save(OUT_DIR / f"{stem}_ref_ship_q75.png")

            print(f"  fetched {name} z{z}")

    (OUT_DIR / "elev_index.json").write_text(json.dumps(elev_index, indent=2))
    # Per-area DEM bytes, so spike_baked_contours.mjs can calibrate its
    # relief bias against the one corridor-wide anchor that exists: the
    # published mean bytes/tile of each band.
    (OUT_DIR / "dem_bytes.json").write_text(
        json.dumps({str(z): {n: b for n, b in zip(AREAS, dem_bytes[z])} for z in ZOOMS}, indent=2)
    )
    (OUT_DIR / "bake_bytes.json").write_text(
        json.dumps(
            {
                f"{z}|{'lossless' if q is None else q}": {n: b for n, b in zip(AREAS, bake_bytes[z][q])}
                for z in ZOOMS
                for q in (None, *QUALITIES)
            },
            indent=2,
        )
    )

    def mean(v: list[float]) -> float:
        return sum(v) / len(v)

    say("RIG CHECK - arm A against the published archive (bytes/tile)")
    say(f"{'zoom':>5} {'sample KB':>10} {'published KB':>13} {'delta':>8}")
    for z in ZOOMS:
        tiles, mb = PUBLISHED[z]
        pub_kb = mb * 1e6 / tiles / 1024
        smp_kb = mean(dem_bytes[z]) / 1024
        say(f"{'z%d' % z:>5} {smp_kb:>10.1f} {pub_kb:>13.1f} {(smp_kb / pub_kb - 1) * 100:>7.1f}%")
    say()

    say("BYTES - centre tile, mean over 6 areas")
    header = f"{'zoom':>5} {'DEM (A)':>10}" + "".join(
        f"{('lossless' if q is None else 'q%d' % q):>10}" for q in (None, *QUALITIES)
    )
    say(header)
    for z in ZOOMS:
        row = f"{'z%d' % z:>5} {mean(dem_bytes[z]) / 1024:>9.1f}K"
        for q in (None, *QUALITIES):
            row += f"{mean(bake_bytes[z][q]) / 1024:>9.1f}K"
        say(row)
    say()

    say("BYTE RATIO - baked hillshade / shipped DEM tile")
    say(f"{'zoom':>5}" + "".join(f"{('lossless' if q is None else 'q%d' % q):>10}" for q in (None, *QUALITIES)))
    for z in ZOOMS:
        row = f"{'z%d' % z:>5}"
        for q in (None, *QUALITIES):
            row += f"{mean(bake_bytes[z][q]) / mean(dem_bytes[z]):>10.3f}"
        say(row)
    say()

    say("FIDELITY - % of hillshade pixels shifted >8/255 vs unquantized truth")
    say("(the shipped 0.5 m floor is the baseline every prior decision used)")
    say(f"{'zoom':>5} {'shipped':>9}" + "".join(f"{'q%d' % q:>9}" for q in QUALITIES))
    for z in ZOOMS:
        row = f"{'z%d' % z:>5} {mean([b for _, b in ship_fid[z]]):>8.2f}%"
        for q in QUALITIES:
            row += f"{mean([b for _, b in fidelity[z][q]]):>8.2f}%"
        say(row)
    say()

    say(f"OVERZOOMED {OVERZOOM}x - the regime the client displays (z13 to z15)")
    say("baked 'lossless' isolates shade-then-magnify from any codec error")
    say(f"{'zoom':>5} {'shipped':>9} {'lossless':>9}" + "".join(f"{'q%d' % q:>9}" for q in QUALITIES))
    for z in ZOOMS:
        row = f"{'z%d' % z:>5} {mean([b for _, b in over_ship[z]]):>8.2f}%"
        for q in (None, *QUALITIES):
            row += f"{mean([b for _, b in over_bake[z][q]]):>8.2f}%"
        say(row)
    say()

    say("PER-AREA at q75, native - worst case is what decides this")
    say(f"{'area':>22} " + " ".join(f"{'z%d' % z:>8}" for z in ZOOMS))
    for i, name in enumerate(AREAS):
        say(f"{name:>22} " + " ".join(f"{fidelity[z][75][i][1]:>7.2f}%" for z in ZOOMS))
    say()

    say("PROJECTION - hillshade half only, applied to published per-zoom MB")
    say("reasoned: per-zoom byte RATIO from this sample x the published band")
    for q in (None, *QUALITIES):
        total = PUBLISHED_SHALLOW_MB
        for z in ZOOMS:
            total += PUBLISHED[z][1] * mean(bake_bytes[z][q]) / mean(dem_bytes[z])
        label = "lossless" if q is None else f"q{q}"
        say(f"  {label:>9}: {total:>7.1f} MB of baked hillshade (vs 275.6 MB dem.pmtiles)")
    say()
    say("Contours are NOT in that projection - see spike_baked_contours.mjs.")
    say("A baked hillshade alone does not let the DEM be dropped, because the")
    say("contour generator reads the same elevation tiles.")

    (OUT_DIR / "report.txt").write_text("\n".join(report) + "\n")
    print(f"\nwrote {OUT_DIR / 'report.txt'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--images", action="store_true", help="write triptychs to look at")
    main(p.parse_args())
