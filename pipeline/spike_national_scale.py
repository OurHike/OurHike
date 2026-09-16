"""What would the sheet cost if it covered every trail, not just the A.T.?

`lib/build_regions.py` states the gap in one sentence: the trail lines were cut
into 1-degree coverage cells nationwide by #1257 and **525 cells hold a tile**,
while the sheet under them reaches **62**. So the phone can already draw other
organizations' lines over most of the country and has ground to draw them on
over a thin band of it. This prices closing that.

WHY THE A.T.'s OWN BYTES/TILE CANNOT JUST BE MULTIPLIED. The corridor is
mountainous and mountains compress worst - LIGHT_DOWNLOAD.md's whole projection
method rests on that, and its own six-area sample runs 6-16% dense against the
published mean for exactly this reason. Most of the United States is not the
Appalachians. So this measures the DEM's cost per unit ground across REAL CONUS
terrain, sampled across the kinds of it there actually are, rather than assuming
the corridor generalises.

WHAT IT MEASURES, AND WHAT IT ONLY BOUNDS

  measured  bytes per tile, by terrain, through export_dem.encode_tile itself -
            so this is the shipping transform at the shipping quantize step,
            not a reimplementation of either.
  reasoned  the CONUS total: measured bytes/tile times a tile count derived from
            land area and web-mercator tile geometry. That is an upper bound on
            any trail-shaped build and a poor estimate of one, because a
            corridor is a thin ribbon and this is a filled continent.
  reasoned  the cell total, which is the figure a trail-shaped build actually
            lands near: today's published cells, scaled to 525.

THE SAMPLE IS DELIBERATELY NOT CORRIDOR-SHAPED and its weighting is its main
weakness, stated here rather than buried: twelve low-relief points against
twelve mountainous ones, where the real country is flatter than that. So the
CONUS mean below is high, the total is high with it, and both are bounds in the
safe direction for a question about whether something fits.

Outputs land in data/spike_national_scale/report.txt.
"""

import argparse
import json
import math
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from export_dem import DEM_TILE_URL, QUANTIZE_STEP_M, encode_tile, quantize_unit
from lib.http_retry import request_with_retry

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "data" / "spike_national_scale"

# Sampled across the kinds of ground the United States is made of, not across
# the kinds a trail corridor is made of. Half of these are places no long trail
# goes, which is the point: a national build covers the country between the
# trails as well as the ridges along them.
LOW_RELIEF = {
    "great_plains_ks": (38.5, -99.0),
    "corn_belt_ia": (42.0, -93.5),
    "gulf_coast_la": (30.0, -92.0),
    "florida_fl": (28.5, -81.5),
    "delta_ms": (33.5, -90.5),
    "high_plains_ne": (41.5, -101.0),
    "west_tx": (31.5, -102.5),
    "central_valley_ca": (36.5, -120.0),
    "palouse_wa": (46.8, -117.5),
    "ohio_valley_oh": (39.8, -83.0),
    "piedmont_nc": (35.8, -79.5),
    "upper_mi": (46.3, -87.5),
}
HIGH_RELIEF = {
    "rockies_co": (39.5, -106.3),
    "sierra_ca": (37.8, -119.4),
    "cascades_wa": (46.9, -121.6),
    "wasatch_ut": (40.6, -111.6),
    "bitterroot_mt": (46.0, -114.3),
    "sangre_nm": (36.0, -105.6),
    "ozarks_ar": (35.9, -93.3),
    "adirondacks_ny": (44.1, -74.0),
    "smokies_tn": (35.6, -83.5),
    "black_hills_sd": (43.9, -103.5),
    "mojave_nv": (36.5, -115.5),
    "columbia_or": (44.5, -121.0),
}
AREAS = {**LOW_RELIEF, **HIGH_RELIEF}

# The bands the taper actually buys. z0-10 is 41.2 MB of the A.T.'s 275.6 and
# does not scale with coverage the way the deep bands do.
ZOOMS = (11, 12, 13)
GRID = 2  # 2x2 tiles per area per zoom - enough to average out one odd tile

# The A.T. corridor's own measured mean bytes/tile per band, from the built
# archive (LIGHT_DOWNLOAD.md, run 33065213666): tiles, MB.
AT_BANDS = {11: (1139, 49.3), 12: (2315, 78.8), 13: (4054, 106.2)}

# CONUS land area, USGS. Tile ground area is computed at the area-weighted mean
# latitude rather than per-tile: web-mercator tiles shrink with latitude, and
# 39N is where the country's land actually sits.
CONUS_LAND_KM2 = 8.08e6
CONUS_MEAN_LAT = 39.0
EARTH_CIRCUMFERENCE_KM = 40075.017

# What lib/build_regions.py records, and the whole reason for this file. Both
# are READ BACK from the bucket below rather than trusted from here: the 525 in
# that docstring is already stale, and a scoping number nobody re-checks is how
# a document starts lying quietly.
DOCUMENTED_CELLS_WITH_TRAIL_LINES = 525

# The cell families as published. `*_cell_*` is the 1-degree graticule unit
# cut_cells.py cuts today; `*_stretch_*` is the trail-derived cut it superseded
# (#1175) and still sits in the bucket under its old keys. Reading the wrong one
# is an easy mistake with a 40% error in it, so the prefixes are named here.
DEM_CELL_PREFIX = "dem_cell_"
TRAIL_CELL_PREFIX = "nearby_trails_cell_"

LATEST_JSON = "https://data.ourhike.org/latest.json"


def tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2**z
    lat_r = math.radians(lat)
    return (
        int((lon + 180.0) / 360.0 * n),
        int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n),
    )


def tile_side_km(zoom: int, lat: float = CONUS_MEAN_LAT) -> float:
    return EARTH_CIRCUMFERENCE_KM * math.cos(math.radians(lat)) / 2**zoom


def measure_areas(session: requests.Session, unit: int) -> dict[tuple[str, int], list[int]]:
    """Encoded bytes for every sampled tile, through the shipping transform."""
    jobs = []
    for name, (lat, lon) in AREAS.items():
        for zoom in ZOOMS:
            cx, cy = tile_xy(lat, lon, zoom)
            for dx in range(GRID):
                for dy in range(GRID):
                    jobs.append((name, zoom, (zoom, cx + dx, cy + dy)))

    def one(zxy: tuple[int, int, int]) -> int:
        resp = request_with_retry(DEM_TILE_URL.format(z=zxy[0], x=zxy[1], y=zxy[2]), session=session, label=f"dem z{zxy[0]}")
        return len(encode_tile(resp.content, unit))

    with ThreadPoolExecutor(max_workers=16) as pool:
        sizes = list(pool.map(one, [j[2] for j in jobs]))
    out: dict[tuple[str, int], list[int]] = {}
    for (name, zoom, _), size in zip(jobs, sizes):
        out.setdefault((name, zoom), []).append(size)
    return out


def published_cells() -> dict | None:
    """What the bucket actually holds, or None where it cannot be reached.

    Read rather than remembered, for both halves of the ratio: how many cells
    have a DEM under them and how many hold trail lines at all. The second is
    the number lib/build_regions.py wrote down as 525 and the trail network has
    grown since."""
    try:
        artifacts = requests.get(LATEST_JSON, timeout=30).json().get("artifacts", {})
    except Exception:
        return None

    def family(prefix: str) -> tuple[int, int]:
        keys = [k for k in artifacts if k.startswith(prefix) and k.endswith(".pmtiles")]
        return len(keys), sum(artifacts[k].get("size_bytes", 0) for k in keys)

    dem_count, dem_bytes = family(DEM_CELL_PREFIX)
    trail_count, _ = family(TRAIL_CELL_PREFIX)
    if not dem_count or not trail_count:
        return None
    return {"dem_cells": dem_count, "dem_bytes": dem_bytes, "trail_cells": trail_count}


def main(args: argparse.Namespace) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: list[str] = []

    def say(line: str = "") -> None:
        print(line)
        report.append(line)

    unit = quantize_unit(QUANTIZE_STEP_M)
    by_area = measure_areas(requests.Session(), unit)

    say("NATIONAL SCALE - what the DEM costs per unit ground, off the corridor")
    say(f"{len(AREAS)} areas x {len(ZOOMS)} zooms x {GRID**2} tiles, quantize {QUANTIZE_STEP_M} m")
    say()
    say(f"{'area':>22} " + " ".join(f"{'z%d' % z:>9}" for z in ZOOMS))
    for group, label in ((LOW_RELIEF, "low relief"), (HIGH_RELIEF, "high relief")):
        say(f"-- {label}")
        for name in group:
            row = " ".join(f"{statistics.mean(by_area[(name, z)]) / 1024:>8.1f}K" for z in ZOOMS)
            say(f"{name:>22} {row}")
    say()

    conus_kb: dict[int, float] = {}
    say(f"{'zoom':>6} {'low KB':>9} {'high KB':>9} {'sample KB':>11} {'A.T. KB':>9} {'vs A.T.':>8}")
    for zoom in ZOOMS:
        low = statistics.mean(b for n in LOW_RELIEF for b in by_area[(n, zoom)]) / 1024
        high = statistics.mean(b for n in HIGH_RELIEF for b in by_area[(n, zoom)]) / 1024
        mean = statistics.mean(b for n in AREAS for b in by_area[(n, zoom)]) / 1024
        conus_kb[zoom] = mean
        at_tiles, at_mb = AT_BANDS[zoom]
        at_kb = at_mb * 1e6 / at_tiles / 1024
        say(f"{'z%d' % zoom:>6} {low:>9.1f} {high:>9.1f} {mean:>11.1f} {at_kb:>9.1f} {mean / at_kb:>8.2f}")
    say()
    say("Low relief is 2-4x cheaper per tile than high. That spread is the whole")
    say("reason the corridor's own bytes/tile cannot be multiplied out to a country.")
    say()

    say("CEILING - filled CONUS coverage at every zoom the taper reaches")
    say(f"{'zoom':>6} {'tile km':>9} {'tile km2':>10} {'tiles':>12} {'GB':>8}")
    total_gb = 0.0
    for zoom in ZOOMS:
        side = tile_side_km(zoom)
        tiles = CONUS_LAND_KM2 / side**2
        gb = tiles * conus_kb[zoom] * 1024 / 1e9
        total_gb += gb
        say(f"{'z%d' % zoom:>6} {side:>9.2f} {side**2:>10.1f} {tiles:>12,.0f} {gb:>8.2f}")
    say(f"{'':>6} {'':>9} {'':>10} {'total':>12} {total_gb:>8.1f}")
    say()
    say("An UPPER BOUND on any trail-shaped build and a poor estimate of one: a")
    say("corridor is a ribbon, this is a filled continent. It answers 'does the")
    say("worst case fit', which for storage it comfortably does.")
    say()

    cells = published_cells()
    if cells is None:
        say("REALISTIC - skipped, the bucket could not be read")
    else:
        per_cell = cells["dem_bytes"] / cells["dem_cells"]
        trail_cells = cells["trail_cells"]
        at_kb13 = AT_BANDS[13][1] * 1e6 / AT_BANDS[13][0] / 1024
        high_kb13 = statistics.mean(b for n in HIGH_RELIEF for b in by_area[(n, 13)]) / 1024
        say("REALISTIC - the cells actually published, scaled to the ground trails cover")
        say(
            f"  DEM cells published today : {cells['dem_cells']} cells, "
            f"{cells['dem_bytes'] / 1e6:.1f} MB, mean {per_cell / 1e6:.2f} MB"
        )
        say(
            f"  cells holding trail lines : {trail_cells} (live), "
            f"against {DOCUMENTED_CELLS_WITH_TRAIL_LINES} in lib/build_regions.py"
        )
        say(f"  cells still needing one   : {trail_cells - cells['dem_cells']}")
        flat = trail_cells * per_cell / 1e9
        say(f"  at today's mean per cell  : {flat:.1f} GB")
        say(f"  repriced for western relief: {flat * high_kb13 / at_kb13:.1f} GB")
        say("  (the second row prices a cell at the sampled HIGH-relief mean, not")
        say("   the overall CONUS one: trails are where the mountains are, so a")
        say("   trail-shaped national build skews expensive, never toward the plains)")
    say()
    say("Storage is not the constraint at any of these numbers: R2 is $0.015/GB")
    say("-month after 10 GB free, and egress is $0 however many hikers download.")
    say("What binds is build capacity (BASEMAP.md marks whole-US Planetiler")
    say("marginal on a free runner and North America unable to fit) and the")
    say("client's ability to read cells at all (#1475).")

    (OUT_DIR / "report.txt").write_text("\n".join(report) + "\n")
    (OUT_DIR / "bytes.json").write_text(json.dumps({f"{n}|{z}": v for (n, z), v in by_area.items()}, indent=2))
    print(f"\nwrote {OUT_DIR / 'report.txt'}")


if __name__ == "__main__":
    main(argparse.ArgumentParser(description=__doc__).parse_args())
