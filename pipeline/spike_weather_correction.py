"""Build step 2 of features/WEATHER.md: score the correction the phone will run (#1056).

WHY THIS EXISTS. The maintainer chose HRRR corrected for elevation for the
first two days' temperature (2026-09-24) on the strength of one number: 2.3 °F
mean error in tomorrow's high, against NBM's 2.7 °F, from
`spike_weather_sources.py`. That number is Open-Meteo's - its archive of
"HRRR", its choice of which run and which grid cell, its correction to its
own 90 m DEM - and WEATHER.md §3 marks it @unvalidated for the thing we
ship. This spike scores the thing we ship instead:

- **HRRR as the job publishes it.** The real run, from NOAA's own archive on
  AWS (`noaa-hrrr-bdp-pds`), decoded by rasterio exactly as `fetch_hrrr.py`
  and `export_weather.py` do, at the cell `lib/hrrr_grid.cells` puts the
  station in, with the water rule's borrow, rounded to 0.1 °C and the
  cell height to the metre as the cell files carry them.
- **The phone's arithmetic.** `correct()` below: the cell's temperature
  minus a fixed lapse rate times the height from the cell's model height up
  to the point's. Scored with the point's height as IEM records the station's
  elevation, because that is the height the observed temperature was taken
  at, and again with the height the phone would read: the terrain tiles the
  app ships (USGS 3DEP via AWS Terrain Tiles, terrarium, zoom 13 -
  `export_dem.py`) at IEM's coordinate. The two differ where IEM gives the
  coordinate to two decimals (~1 km): Wolf Creek Pass reads 3,380 m in the
  DEM against the station's 3,584 m. That second score is therefore a
  measure of what a wrong point height costs, not a better answer.
- **NBM as the job publishes it**, from its own archive (`noaa-nbm-pds`), at
  the square `lib/nbm_grid.squares` puts the station in, with the water rule.
  Scored raw, as it ships, and corrected from URMA's terrain for comparison
  with §3's finding that correcting NBM makes it worse.

TWO WINDOWS, BECAUSE ONE VARIANT CAME AFTER THE FIRST ANSWER. The first
window is the first spike's (2026-07-24 to 09-22). On it, corrected HRRR beat
NBM on highs and lost on lows, and averaging the two models hour by hour
("blend") beat NBM on both. The blend was thought of after seeing that, so a
score on the same days is not evidence for it. The second window
(2026-05-24 to 07-23, the 61 days before, and after NBM v5.0 went live on
05-05) was scored after the blend was defined and is the out-of-sample test.
Run it with --start 2026-05-24 --end 2026-07-23.

THE LAPSE RATE WAS FIXED BEFORE SCORING. `LAPSE_C_PER_KM` is 6.5, the
standard atmosphere's, chosen because it is the textbook default and not
because of anything in this data. `SENSITIVITY` re-scores 5.0 and 8.0 so a
reader can see how much the answer depends on the choice. Picking whichever
of those scored best would be fitting the rate to the 61 days it is then
judged on, so this does not do that.

WHAT "TOMORROW'S HIGH" MEANS HERE. For each local day D, the 12 UTC run of the
day before - the run a phone would hold on the evening before a hike -
forecast hours 13 to 44, which cover the whole of day D at every station's
offset (UTC-4 to UTC-7). A day's high and low are the extremes over that
local day, by `spike_weather_sources.daily_extremes`, against IEM's
observations from the same stations and window as the first spike, scored
by its `score`. Only day D is kept from each run.

SAME LIMITS AS THE FIRST SPIKE, stated again because they bind harder here:
summer only (a fixed lapse rate is at its worst in winter inversions - build
step 6), eight stations chosen for relief rather than at random, and one run
a day.

THIS IS A SPIKE. The downloading is throwaway; the answer is the output.

    python spike_weather_correction.py                 (the first spike's window)
    python spike_weather_correction.py --start 2026-07-24 --end 2026-09-22

Samples are cached under data/spike_weather/, so a re-run is offline. The
first run downloads ~3.7 GB (61 runs x 32 hours, HRRR's 2 m temperature by
byte range and NBM's temperature GeoTIFF whole) and keeps none of it.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
import requests
from PIL import Image
from rasterio.io import MemoryFile

import spike_weather_sources as first
from build_weather_squares import BORROW_RINGS, borrow_land, grib_message_range, nbm_centres_on_hrrr, water_mask
from lib import hrrr_grid, nbm_grid

ROOT = Path(__file__).resolve().parent
CACHE = first.CACHE
WEATHER_RAW = ROOT / "data" / "raw" / "weather"
HRRR_HEIGHT_PATH = WEATHER_RAW / "hrrr_height.grb2"
HRRR_LAND_PATH = WEATHER_RAW / "hrrr_land.grb2"
URMA_TERRAIN_PATH = WEATHER_RAW / "urma_terrain.grb2"

HRRR_BUCKET = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
NBM_BUCKET = "https://noaa-nbm-pds.s3.amazonaws.com"
TERRAIN_TILE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
USER_AGENT = first.USER_AGENT

RUN_HOUR = 12
FORECAST_HOURS = range(13, 45)
DEM_ZOOM = 13  # export_dem.MAX_ZOOM: the deepest terrain the app ships
DEM_QUANTUM_M = 0.5  # export_dem's quantize step

LAPSE_C_PER_KM = 6.5
SENSITIVITY = (5.0, 6.5, 8.0)

THREADS = 8


# --------------------------------------------------------------------------
# Pure pieces - what the tests pin.


def correct(temp_c: float, cell_height_m: float, point_height_m: float, lapse_c_per_km: float = LAPSE_C_PER_KM) -> float:
    """The phone's correction: cooler going up, warmer going down, at a
    fixed rate from the model's height to the point's."""
    return temp_c - lapse_c_per_km * (point_height_m - cell_height_m) / 1000.0


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def runs(start: date, end: date) -> list[datetime]:
    """The run scored for each local day from `start` to `end`: 12 UTC on
    the day before."""
    days = (end - start).days + 1
    return [
        datetime.combine(start - timedelta(days=1) + timedelta(days=k), datetime.min.time(), UTC).replace(hour=RUN_HOUR)
        for k in range(days)
    ]


def scored_day(run: datetime) -> date:
    return (run + timedelta(days=1)).date()


def terrarium_metres(r: int, g: int, b: int) -> float:
    """Terrarium's encoding, floored to the app's quantum as export_dem.py
    stores it."""
    raw = r * 256 + g + b / 256 - 32768
    return math.floor(raw / DEM_QUANTUM_M) * DEM_QUANTUM_M


def tile_pixel(lon: float, lat: float, zoom: int = DEM_ZOOM) -> tuple[int, int, int, int]:
    """(tile x, tile y, pixel x, pixel y) of a point in a 256-pixel web
    mercator tile at `zoom`."""
    n = 2**zoom
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return int(x), int(y), int((x - int(x)) * 256), int((y - int(y)) * 256)


def extremes_for_day(readings: list[tuple[datetime, float]], utc_offset_s: int, day: date) -> tuple[float, float] | None:
    return first.daily_extremes(readings, utc_offset_s).get(day)


# --------------------------------------------------------------------------
# Where each station reads from, by the job's own rules.


def hrrr_reads(stations) -> dict[str, tuple[int, int, int]]:
    """{sid: (hrrr row, hrrr col, cell height m)}, water cells borrowed."""
    with rasterio.open(HRRR_HEIGHT_PATH) as ds:
        height = ds.read(1)
    with rasterio.open(HRRR_LAND_PATH) as ds:
        land = ds.read(1)
    rows, cols = hrrr_grid.cells([s.lon for s in stations], [s.lat for s in stations])
    cells = {(int(r), int(c)) for r, c in zip(rows, cols, strict=True)}
    borrowed, _ = borrow_land(cells, land == 0, BORROW_RINGS)
    out = {}
    for s, r, c in zip(stations, rows.tolist(), cols.tolist(), strict=True):
        rr, rc = borrowed.get((r, c), (r, c))
        out[s.sid] = (rr, rc, int(round(float(height[rr, rc]))))
    return out


def nbm_reads(stations) -> dict[str, tuple[int, int, float]]:
    """{sid: (nbm row, nbm col, URMA terrain m)}, water squares borrowed."""
    with rasterio.open(URMA_TERRAIN_PATH) as ds:
        terrain = ds.read(1).astype(np.float64)
    with rasterio.open(HRRR_LAND_PATH) as ds:
        land = ds.read(1)
    hrows, hcols = nbm_centres_on_hrrr()
    water = water_mask(terrain, land, hrows, hcols)
    rows, cols = nbm_grid.squares([s.lon for s in stations], [s.lat for s in stations])
    squares = {(int(r), int(c)) for r, c in zip(rows, cols, strict=True)}
    borrowed, _ = borrow_land(squares, water, BORROW_RINGS)
    out = {}
    for s, r, c in zip(stations, rows.tolist(), cols.tolist(), strict=True):
        rr, rc = borrowed.get((r, c), (r, c))
        out[s.sid] = (rr, rc, float(terrain[rr, rc]))
    return out


# --------------------------------------------------------------------------
# Network, cached.


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def _get(session: requests.Session, url: str, **kw) -> requests.Response:
    """GET with four tries on transient faults. A 404 raises at once: the
    archive does not have that file, and asking again will not change it."""
    for attempt in range(4):
        try:
            response = session.get(url, timeout=120, **kw)
        except requests.ConnectionError:
            time.sleep(2**attempt)
            continue
        if response.status_code in (200, 206):
            return response
        if response.status_code == 404:
            response.raise_for_status()
        time.sleep(2**attempt)
    raise requests.ConnectionError(f"gave up on {url}")


def dem_heights(stations) -> dict[str, float]:
    path = CACHE / "dem_heights_z13.json"
    if path.exists():
        return json.loads(path.read_text())
    session = _session()
    out = {}
    for s in stations:
        tx, ty, px, py = tile_pixel(s.lon, s.lat)
        png = _get(session, TERRAIN_TILE.format(z=DEM_ZOOM, x=tx, y=ty)).content
        r, g, b = Image.open(io.BytesIO(png)).convert("RGB").getpixel((px, py))
        out[s.sid] = terrarium_metres(r, g, b)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return out


def sample_hrrr(session, run: datetime, hour: int, reads: dict) -> dict[str, float]:
    key = f"hrrr.{run:%Y%m%d}/conus/hrrr.t{run:%H}z.wrfsfcf{hour:02d}.grib2"
    index = _get(session, f"{HRRR_BUCKET}/{key}.idx").text.splitlines()
    start, end = grib_message_range(index, "TMP", "2 m above ground")
    body = _get(session, f"{HRRR_BUCKET}/{key}", headers={"Range": f"bytes={start}-{end}"}).content
    with MemoryFile(body) as mem, mem.open() as ds:
        if not hrrr_grid.matches(ds.transform, ds.crs, ds.width, ds.height) or ds.tags(1).get("GRIB_UNIT") != "[C]":
            raise RuntimeError(f"{key} is not HRRR's pinned grid in Celsius")
        grid = ds.read(1)
    return {sid: round(float(grid[r, c]), 1) for sid, (r, c, _) in reads.items()}


def sample_nbm(session, run: datetime, hour: int, reads: dict) -> dict[str, float | None]:
    valid = run + timedelta(hours=hour)
    key = f"blendv5.0/conus/{run:%Y/%m/%d/%H}00/temp/blendv5.0_conus_temp_{run:%Y-%m-%dT%H:%M}_{valid:%Y-%m-%dT%H:%M}.tif"
    body = _get(session, f"{NBM_BUCKET}/{key}").content
    with MemoryFile(body) as mem, mem.open() as ds:
        if not nbm_grid.matches(ds.transform, ds.crs, ds.width, ds.height):
            raise RuntimeError(f"{key} is not NBM's pinned grid")
        grid, nodata = ds.read(1), ds.nodata
    out = {}
    for sid, (r, c, _) in reads.items():
        v = float(grid[r, c])
        out[sid] = None if (nodata is not None and v == nodata) else v
    return out


def migrate(old: dict) -> dict[str, dict[str, dict | None]]:
    """The first cache layout ({run: {sid: [[valid, value], ...]}}) in the
    current one, keeping only the hours it actually holds."""
    out: dict[str, dict[str, dict | None]] = {}
    for run_iso, by_sid in old.items():
        run = datetime.fromisoformat(run_iso)
        for sid, series in by_sid.items():
            for valid, value in series:
                hour = int((datetime.fromisoformat(valid) - run).total_seconds() // 3600)
                out.setdefault(run_iso, {}).setdefault(str(hour), {})[sid] = value
    return out


def archive(model: str, run_list: list[datetime], reads: dict) -> dict[str, dict[str, dict | None]]:
    """{run iso: {forecast hour: {sid: value}, or None where the archive has
    no file}}, cached per run and hour so an interrupted run resumes exactly
    where it stopped."""
    stem = f"{model}_{run_list[0]:%Y%m%d}_{run_list[-1]:%Y%m%d}"
    path = CACHE / f"archive_v2_{stem}.json"
    old = CACHE / f"archive_{stem}.json"
    if path.exists():
        cached = json.loads(path.read_text())
    elif old.exists():
        cached = migrate(json.loads(old.read_text()))
    else:
        cached = {}
    sampler = sample_hrrr if model == "hrrr" else sample_nbm
    session = _session()
    jobs = [(run, h) for run in run_list for h in FORECAST_HOURS if str(h) not in cached.get(run.isoformat(), {})]

    def one(job):
        run, hour = job
        try:
            return run, hour, sampler(session, run, hour, reads)
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                return run, hour, None
            raise

    CACHE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(THREADS) as pool:
        for n, (run, hour, values) in enumerate(pool.map(one, jobs), 1):
            cached.setdefault(run.isoformat(), {})[str(hour)] = values
            if n % 64 == 0:
                print(f"  {model}: {n}/{len(jobs)} messages")
                path.write_text(json.dumps(cached))
    path.write_text(json.dumps(cached))
    return cached


def series(cached: dict, run: datetime, sid: str) -> list[tuple[datetime, float]]:
    """One station's hours from one run, missing files and missing values
    left out rather than filled."""
    hours = cached.get(run.isoformat(), {})
    return [
        (run + timedelta(hours=int(h)), values[sid])
        for h, values in sorted(hours.items(), key=lambda kv: int(kv[0]))
        if values is not None and values.get(sid) is not None
    ]


def missing_files(cached: dict) -> list[str]:
    return sorted(f"{run} +{h}h" for run, hours in cached.items() for h, v in hours.items() if v is None)


# --------------------------------------------------------------------------


def readings(pairs: list[tuple[datetime, float]], transform) -> list[tuple[datetime, float]]:
    return [(t, transform(v)) for t, v in pairs]


def blend(a: list[tuple[datetime, float]], b: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """The mean of two series hour by hour, over the hours both have."""
    other = dict(b)
    return [(t, (v + other[t]) / 2) for t, v in a if t in other]


BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 1056


def paired_difference(errors: dict[date, list[tuple[float, float]]], seed: int = BOOTSTRAP_SEED) -> tuple[float, float, float]:
    """(mean, 2.5th, 97.5th percentile) of |error a| - |error b| over
    station-days, resampling whole days so the stations sharing a day's
    weather move together. `errors` is {day: [(error a, error b), ...]}.
    Negative means a was closer."""
    import random

    days = sorted(errors)
    per_day = {d: [abs(a) - abs(b) for a, b in errors[d]] for d in days}
    point = sum(x for d in days for x in per_day[d]) / sum(len(per_day[d]) for d in days)
    rng = random.Random(seed)
    boots = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [x for d in (rng.choice(days) for _ in days) for x in per_day[d]]
        boots.append(sum(sample) / len(sample))
    boots.sort()
    return point, boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 24))
    ap.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 22))
    args = ap.parse_args()

    stations = first.STATIONS
    run_list = runs(args.start, args.end)
    dem = dem_heights(stations)
    h_reads = hrrr_reads(stations)
    n_reads = nbm_reads(stations)
    print(
        f"Window {args.start} .. {args.end}: {len(run_list)} runs at {RUN_HOUR:02d}Z the day before, hours {FORECAST_HOURS.start}-{FORECAST_HOURS.stop - 1}\n"
    )
    print(f"{'station':6} {'IEM m':>6} {'DEM z13 m':>9} {'HRRR cell':>12} {'cell m':>6} {'NBM square':>12} {'URMA m':>6}")
    for s in stations:
        hr, hc, hh = h_reads[s.sid]
        nr, nc, nh = n_reads[s.sid]
        print(f"{s.sid:6} {s.elev_m:6.0f} {dem[s.sid]:9.1f} {f'({hr},{hc})':>12} {hh:6d} {f'({nr},{nc})':>12} {nh:6.0f}")

    hrrr = archive("hrrr", run_list, h_reads)
    nbm = archive("nbm", run_list, n_reads)
    for model, cached in (("HRRR", hrrr), ("NBM", nbm)):
        gone = missing_files(cached)
        print(f"{model}: {len(gone)} of {len(run_list) * len(FORECAST_HOURS)} forecast files missing from the archive {gone[:6]}")

    variants = [
        "NBM raw",
        "NBM corrected 6.5",
        "HRRR raw",
        *(f"HRRR corrected {g}" for g in SENSITIVITY),
        "HRRR corr 6.5 to DEM",
        "blend 6.5",
    ]
    print("\nTomorrow's high / low, error in F: MAE (bias forecast - observed), n days\n")
    head = f"{'station':6} {'n':>3} " + " ".join(f"{v:>21}" for v in variants)
    print(head)
    per_station = {}
    paired: dict[str, dict[str, dict[date, list]]] = {}
    for s in stations:
        obs = first.daily_extremes(first.observations(s, args.start, args.end), s.utc_offset_s)
        _, _, cell_h = h_reads[s.sid]
        _, _, square_h = n_reads[s.sid]
        point_h = s.elev_m
        fc: dict[str, dict[date, tuple[float, float]]] = {v: {} for v in variants}
        for run in run_list:
            day = scored_day(run)
            h_series = series(hrrr, run, s.sid)
            n_series = series(nbm, run, s.sid)
            pairs = {
                "NBM raw": readings(n_series, lambda f: f),
                "NBM corrected 6.5": readings(n_series, lambda f: c_to_f(correct((f - 32) * 5 / 9, square_h, point_h))),
                "HRRR raw": readings(h_series, c_to_f),
            }
            for g in SENSITIVITY:
                pairs[f"HRRR corrected {g}"] = readings(h_series, lambda c, g=g: c_to_f(correct(c, cell_h, point_h, g)))
            pairs["HRRR corr 6.5 to DEM"] = readings(h_series, lambda c: c_to_f(correct(c, cell_h, dem[s.sid])))
            pairs["blend 6.5"] = blend(pairs["HRRR corrected 6.5"], pairs["NBM raw"])
            for v, rs in pairs.items():
                ext = extremes_for_day(rs, s.utc_offset_s, day)
                if ext:
                    fc[v][day] = ext
        scores = {v: first.score(fc[v], obs) for v in variants}
        per_station[s.sid] = scores
        for v in variants:
            for k, name in ((0, "high"), (1, "low")):
                for day in set(fc[v]) & set(fc["NBM raw"]) & set(obs):
                    errs = (fc[v][day][k] - obs[day][k], fc["NBM raw"][day][k] - obs[day][k])
                    paired.setdefault(v, {}).setdefault(name, {}).setdefault(day, []).append(errs)
        n = min((sc.n for sc in scores.values() if sc), default=0)
        cells = []
        for v in variants:
            sc = scores[v]
            cells.append(
                f"{sc.high_mae:4.1f}({sc.high_bias:+4.1f})/{sc.low_mae:4.1f}({sc.low_bias:+4.1f})" if sc else f"{'-':>21}"
            )
        print(f"{s.sid:6} {n:3d} " + " ".join(f"{c:>21}" for c in cells))

    print("\nMean over stations (high MAE / low MAE, F):")
    for v in variants:
        ss = [per_station[s.sid][v] for s in stations if per_station[s.sid][v]]
        print(
            f"  {v:22} {sum(x.high_mae for x in ss) / len(ss):4.2f} / {sum(x.low_mae for x in ss) / len(ss):4.2f}   ({len(ss)} stations)"
        )

    print(
        f"\nAgainst NBM raw, paired by station-day: mean |error| difference, F (95% interval, days resampled x{BOOTSTRAP_RESAMPLES}); negative = closer than NBM"
    )
    for v in variants[1:]:
        cells = []
        for name in ("high", "low"):
            days = paired[v][name]
            point, lo, hi = paired_difference(days)
            cells.append(f"{name} {point:+.2f} ({lo:+.2f} .. {hi:+.2f}), n={sum(len(x) for x in days.values())}")
        print(f"  {v:22} " + "   ".join(cells))


if __name__ == "__main__":
    main()
