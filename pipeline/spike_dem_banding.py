"""Does quantizing the DEM band the hillshade? Rendered, not guessed (#186).

export_dem.py floors the terrarium blue channel - sub-meter elevation - to a
step, because on a 10 m 3DEP source that fraction is noise carried at full
entropy. The documented risk (the terrain-RGB literature, and #186's own
acceptance) is that too coarse a step turns gentle slopes into staircases
the hillshade renders as contour-shaped bands. This spike settles the step
from evidence: fetch real tiles over the flattest valley floors the AT
actually crosses, quantize them with the exporter's own floor_blue, render
hillshade at the client's exaggeration, and compare - as images to look at,
and as numbers.

Two regimes, because they answered differently (2026-08-06):

  native      hillshade computed on the z12/z13 grid as those zooms render.
              1 m differs from raw only as diffuse speckle (RMS <= 3.6/255,
              worst area 1.3% of pixels shifted >8/255, no coherent lines) -
              quantization is mostly absorbing sensor noise here.
  overzoomed  the regime the app actually displays: terrain.ts caps the DEM
              at z13 and shows it to z15, so tiles render under 4x bilinear
              magnification. There the 1 m staircase etches visibly across
              the flat ground (7.6% of pixels >8/255 on the flattest window,
              and the eye finds the terracing instantly), while 0.5 m stays
              indistinguishable from unquantized.

Decision recorded from this: QUANTIZE_STEP_M = 0.5 in export_dem.py, at
~1.6x the archive bytes of 1 m (per-block webp ratios 1.54-1.63x).

Outputs land in data/spike_dem_banding/: per-area triptychs
(raw | 1 m | 0.5 m), amplified difference images, the overzoomed worst-case
window, and report.txt with the numbers.
"""

import argparse
import io
import math
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from export_dem import DEM_TILE_URL, floor_blue, quantize_unit

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "data" / "spike_dem_banding"

# The client's hillshade paint at the zooms in question: exaggeration 0.35
# from z12 up (client/src/map/liveTopo.ts HILLSHADE_EXAGGERATION), MapLibre's
# default illumination direction (335) and the conventional 45-degree
# altitude. The absolute shading constants matter less than that all three
# arms render identically - the comparison is raw vs quantized, not this
# renderer vs MapLibre's shader.
EXAGGERATION = 0.35
AZIMUTH_DEG = 335.0
ALTITUDE_DEG = 45.0
TILE_SIZE = 256

# Flat ground is where quantization terraces; mountainsides hide them. Both
# areas are valley floors the trail itself crosses, not hypothetical flats:
# the Cumberland Valley's farmland at Boiling Springs PA, and the Harlem
# Valley floor by the Appalachian Trail Metro-North stop in NY.
AREAS = {
    "cumberland_valley_pa": (40.185, -77.08),
    "harlem_valley_ny": (41.590, -73.590),
}
ZOOMS = (12, 13)
GRID = 3  # 3x3 tiles stitched per area/zoom, so gradients never cross a seam
OVERZOOM = 4  # z13 displayed at z15, the client's cap (map/terrain.ts)


def tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    """Web-mercator tile containing a point - the standard slippy-map math."""
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def meters_per_pixel(lat: float, z: int) -> float:
    return 40075016.686 * math.cos(math.radians(lat)) / (2**z) / TILE_SIZE


def elevation(rgb: np.ndarray) -> np.ndarray:
    """Terrarium decode: (R*256 + G + B/256) - 32768, as float meters."""
    r = rgb[:, :, 0].astype(np.float64)
    g = rgb[:, :, 1].astype(np.float64)
    b = rgb[:, :, 2].astype(np.float64)
    return (r * 256.0 + g + b / 256.0) - 32768.0


def hillshade(elev: np.ndarray, m_per_px: float) -> np.ndarray:
    """Horn's method, grayscale 0-255, slope scaled by the client's
    exaggeration. np.gradient is the central-difference kernel every
    conventional hillshade uses."""
    gy, gx = np.gradient(elev, m_per_px)
    gx = gx * EXAGGERATION * 4.0
    gy = gy * EXAGGERATION * 4.0
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azimuth = math.radians(360.0 - AZIMUTH_DEG + 90.0)
    altitude = math.radians(ALTITUDE_DEG)
    shaded = np.sin(altitude) * np.cos(slope) + np.cos(altitude) * np.sin(slope) * np.cos(azimuth - aspect)
    return np.clip(shaded * 255.0, 0, 255).astype(np.uint8)


def mean_terrace_run(elev: np.ndarray) -> float:
    """Mean horizontal run length of exactly-equal neighboring elevations.

    The tread width of a quantization staircase, in pixels. Raw 10 m data
    keeps runs short (its sub-meter fraction is noisy); flooring stretches
    them, and the stretch is the staircase the hillshade may then draw."""
    eq = elev[:, 1:] == elev[:, :-1]
    starts = eq & ~np.pad(eq, ((0, 0), (1, 0)))[:, :-1]
    runs = int(starts.sum())
    return float(eq.sum()) / max(runs, 1)


def bilinear_upsample(a: np.ndarray, factor: int) -> np.ndarray:
    """What overzooming does to the DEM texture before the shader reads it."""
    img = Image.fromarray(a.astype(np.float32), mode="F")
    return np.asarray(img.resize((a.shape[1] * factor, a.shape[0] * factor), Image.BILINEAR), dtype=np.float64)


def quantized(rgb: np.ndarray, step_m: float) -> np.ndarray:
    return floor_blue(rgb.copy(), quantize_unit(step_m))


def webp_bytes(rgb: np.ndarray) -> int:
    """Lossless-WebP cost of a stitched block, encoded per 256px tile the way
    the exporter ships them."""
    total = 0
    for ty in range(0, rgb.shape[0], TILE_SIZE):
        for tx in range(0, rgb.shape[1], TILE_SIZE):
            buf = io.BytesIO()
            Image.fromarray(rgb[ty : ty + TILE_SIZE, tx : tx + TILE_SIZE]).save(buf, format="WEBP", lossless=True)
            total += buf.getbuffer().nbytes
    return total


def fetch_block(session: requests.Session, lat: float, lon: float, z: int) -> np.ndarray:
    cx, cy = tile_xy(lat, lon, z)
    rows = []
    for dy in range(-(GRID // 2), GRID // 2 + 1):
        cols = []
        for dx in range(-(GRID // 2), GRID // 2 + 1):
            resp = session.get(DEM_TILE_URL.format(z=z, x=cx + dx, y=cy + dy), timeout=60)
            resp.raise_for_status()
            cols.append(np.asarray(Image.open(io.BytesIO(resp.content)).convert("RGB")))
        rows.append(np.concatenate(cols, axis=1))
    return np.concatenate(rows, axis=0)


def flattest_window(elev: np.ndarray, size: int = 192, stride: int = 64) -> tuple[int, int]:
    """Top-left corner of the lowest-stddev window - the worst case for
    banding, since flat ground is where treads grow widest."""
    best: tuple[float, int, int] | None = None
    for oy in range(0, elev.shape[0] - size + 1, stride):
        for ox in range(0, elev.shape[1] - size + 1, stride):
            sd = float(elev[oy : oy + size, ox : ox + size].std())
            if best is None or sd < best[0]:
                best = (sd, oy, ox)
    assert best is not None
    return best[1], best[2]


def compare(h_raw: np.ndarray, h_quantized: np.ndarray) -> tuple[float, float]:
    """(RMS difference on the 0-255 scale, % of pixels shifted >8/255)."""
    diff = h_raw.astype(float) - h_quantized.astype(float)
    rms = float(np.sqrt(np.mean(diff**2)))
    big = float(np.mean(np.abs(diff) > 8) * 100)
    return rms, big


def main(args: argparse.Namespace) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    report: list[str] = []

    for name, (lat, lon) in AREAS.items():
        for z in ZOOMS:
            rgb_raw = fetch_block(session, lat, lon, z)
            rgb_q10 = quantized(rgb_raw, 1.0)
            rgb_q05 = quantized(rgb_raw, 0.5)
            m_per_px = meters_per_pixel(lat, z)

            e_raw, e_q10, e_q05 = elevation(rgb_raw), elevation(rgb_q10), elevation(rgb_q05)
            h_raw, h_q10, h_q05 = (hillshade(e, m_per_px) for e in (e_raw, e_q10, e_q05))

            Image.fromarray(np.concatenate([h_raw, h_q10, h_q05], axis=1)).save(OUT_DIR / f"{name}_z{z}_raw-q1.0-q0.5.png")
            d10 = np.clip(np.abs(h_raw.astype(int) - h_q10.astype(int)) * 8, 0, 255).astype(np.uint8)
            d05 = np.clip(np.abs(h_raw.astype(int) - h_q05.astype(int)) * 8, 0, 255).astype(np.uint8)
            Image.fromarray(np.concatenate([d10, d05], axis=1)).save(OUT_DIR / f"{name}_z{z}_diff8x.png")

            rms10, big10 = compare(h_raw, h_q10)
            rms05, big05 = compare(h_raw, h_q05)
            b_raw, b_q10, b_q05 = webp_bytes(rgb_raw), webp_bytes(rgb_q10), webp_bytes(rgb_q05)
            report.append(
                f"{name} z{z} ({m_per_px:.1f} m/px, elev {e_raw.min():.0f}-{e_raw.max():.0f} m): "
                f"RMS q1.0={rms10:.2f} q0.5={rms05:.2f} | >8/255 q1.0={big10:.2f}% q0.5={big05:.2f}% | "
                f"terrace run px raw={mean_terrace_run(e_raw):.1f} q1.0={mean_terrace_run(e_q10):.1f} "
                f"q0.5={mean_terrace_run(e_q05):.1f} | "
                f"webp q1.0={b_q10 / b_raw:.3f}x raw, q0.5={b_q05 / b_q10:.3f}x of q1.0"
            )

    # The regime the app actually shows: the flattest window of the flattest
    # area, overzoomed the way a z13 DEM tile renders at z15.
    lat, lon = AREAS["cumberland_valley_pa"]
    rgb = fetch_block(session, lat, lon, 13)
    e_all = elevation(rgb)
    oy, ox = flattest_window(e_all)
    window = rgb[oy : oy + 192, ox : ox + 192]
    m_per_px = meters_per_pixel(lat, 13) / OVERZOOM
    panels = [
        hillshade(bilinear_upsample(elevation(arm), OVERZOOM), m_per_px)
        for arm in (window, quantized(window, 1.0), quantized(window, 0.5))
    ]
    Image.fromarray(np.concatenate(panels, axis=1)).save(OUT_DIR / f"overzoom{OVERZOOM}x_flattest_raw-q1.0-q0.5.png")
    rms10, big10 = compare(panels[0], panels[1])
    rms05, big05 = compare(panels[0], panels[2])
    report.append(
        f"overzoomed {OVERZOOM}x flattest window (std {e_all[oy : oy + 192, ox : ox + 192].std():.2f} m): "
        f"RMS q1.0={rms10:.2f} q0.5={rms05:.2f} | >8/255 q1.0={big10:.2f}% q0.5={big05:.2f}%"
    )

    text = "\n".join(report)
    (OUT_DIR / "report.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    main(parser.parse_args())
