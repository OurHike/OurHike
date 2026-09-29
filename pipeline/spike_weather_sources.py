"""Weather-source accuracy spike (#1056, features/WEATHER.md).

Answers three questions, each of which WEATHER.md would otherwise have had
to answer by argument:

  1. **Does forecasting "along each trail", finer than the model's grid,
     buy anything?** Every forecast source is a grid underneath - NBM and
     NWS's NDFD at 2.5 km, HRRR at 3 km, GFS and ECMWF coarser - so a point
     between grid nodes gets a grid value unless somebody corrects it. The
     one correction with physics behind it is temperature against
     elevation (a lapse rate from the grid cell's model height to the
     point's real height). This measures a day-1 forecast's daily high and
     low with that correction and without it, at stations where the two
     heights differ most.
  2. **Which model?** NBM (the blend NWS's own grids start from), HRRR,
     GFS and ECMWF IFS, scored against the same observations.
  3. **How fast does an old forecast go bad?** A phone that last had
     signal N hours ago is reading a forecast issued N hours before the
     day it describes. Scoring the forecasts made one to five days ahead
     of the same days measures what 12+ hours without signal actually
     costs, instead of guessing.

What it scores against: hourly ASOS/AWOS observations from the Iowa
Environmental Mesonet's archive (https://mesonet.agron.iastate.edu/), at a
deliberately lopsided set of stations - Mount Washington's summit, where
the #1056 measurement found two forecast points 3.3 miles apart disagreeing
by 9.2 F, plus valley stations near trails and high passes that the
Pacific Crest and Continental Divide trails cross.

Where the forecasts come from: Open-Meteo's Previous Runs API
(https://open-meteo.com/en/docs/previous-runs-api), which serves what each
model predicted N days ahead for every past hour. Its `elevation=nan`
switch returns the raw grid cell (no correction); by default it corrects
temperature to a 90 m DEM's height at the coordinate. Open-Meteo is used
here as an ARCHIVE, not as a proposed production source - its free tier is
non-commercial, and whether it could ship is WEATHER.md's question.

What this cannot measure, stated so nobody reads more into it:
  - precipitation, wind and thunderstorms - only temperature has a
    correction to test, and hit/miss scoring of precipitation needs more
    than one season;
  - NWS's forecaster-edited NDFD grid, which Open-Meteo does not archive -
    NBM is the blend NDFD starts from, the nearest thing measurable here;
  - any season but the one the window covers. A summer window is the
    kindest one for a lapse rate; winter inversions are where a fixed
    lapse rate is worst, and no summer run can say how much worse.

THIS IS A SPIKE. The HTTP and caching are throwaway; what should survive is
the scoring (daily extremes over a local day, a day counted only when the
station reported enough of it) and the finding.

Run:  python spike_weather_sources.py            (61 days ending yesterday)
      python spike_weather_sources.py --start 2026-07-24 --end 2026-09-22
Responses are cached under data/spike_weather/, so a re-run is offline.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

USER_AGENT = "OurHike-research (github.com/OurHike/OurHike)"
CACHE = Path(__file__).parent / "data" / "spike_weather"

# A day's high or low is only as good as the hours it was taken over. ASOS
# reports hourly and AWOS every 20 minutes, so 18 distinct hours is three
# quarters of a day - @unvalidated: picked so a station with a few missing
# reports still scores, and so a station down for an afternoon (when the
# high happens) does not. What would settle it: re-running at 12 and 22 and
# checking the conclusion does not move.
MIN_HOURS_PER_DAY = 18

MODELS = ("ncep_nbm_conus", "gfs_hrrr", "gfs_global", "ecmwf_ifs025")
LEADS = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Station:
    sid: str
    name: str
    lat: float
    lon: float
    elev_m: float
    why: str
    utc_offset_s: int  # summer (daylight) offset; the default window is all DST


# Coordinates and elevations are IEM's station metadata, read 2026-09-24.
# 0CO's 3,792 m is IEM's figure; Berthoud Pass itself is ~3,450 m, so the
# metadata is doubtful and that station's downscaled score is too.
STATIONS = (
    Station("MWN", "Mount Washington summit", 44.2708, -71.3035, 1910, "A.T. summit", -14400),
    Station("BML", "Berlin, NH", 44.5761, -71.1786, 353, "valley near MWN", -14400),
    Station("LKP", "Lake Placid, NY", 44.2645, -73.9618, 531, "Adirondack valley", -14400),
    Station("GEV", "Ashe County, NC", 36.43, -81.42, 969, "S. Appalachian plateau", -14400),
    Station("SMP", "Stampede Pass, WA", 47.2767, -121.3372, 1209, "PCT pass", -25200),
    Station("CPW", "Wolf Creek Pass, CO", 37.45, -106.80, 3584, "CDT pass", -21600),
    Station("CCU", "Red Cliff Pass, CO", 39.475, -106.153, 3680, "CDT country", -21600),
    Station("0CO", "Berthoud Pass, CO", 39.7939, -105.7639, 3792, "CDT pass", -21600),
)


# --------------------------------------------------------------------------
# Pure scoring - what the tests pin.


def daily_extremes(readings: list[tuple[datetime, float]], utc_offset_s: int) -> dict[date, tuple[float, float]]:
    """Each local day's (high, low), keeping only days with enough hours.

    `readings` are (UTC time, value). A local day is midnight to midnight at
    `utc_offset_s` - a fixed offset, which is exact across a window that
    does not cross a DST change and an hour out at worst when it does.
    """
    by_day: dict[date, list[float]] = defaultdict(list)
    hours: dict[date, set[int]] = defaultdict(set)
    shift = timedelta(seconds=utc_offset_s)
    for t, v in readings:
        local = t + shift
        by_day[local.date()].append(v)
        hours[local.date()].add(local.hour)
    return {d: (max(vals), min(vals)) for d, vals in by_day.items() if len(hours[d]) >= MIN_HOURS_PER_DAY}


@dataclass(frozen=True)
class Score:
    n: int
    high_mae: float
    high_bias: float
    low_mae: float
    low_bias: float


def score(forecast: dict[date, tuple[float, float]], observed: dict[date, tuple[float, float]]) -> Score | None:
    """Mean absolute error and bias (forecast minus observed) of highs and lows,
    over the days both sides have. None when they share no day."""
    days = sorted(set(forecast) & set(observed))
    if not days:
        return None
    dh = [forecast[d][0] - observed[d][0] for d in days]
    dl = [forecast[d][1] - observed[d][1] for d in days]
    n = len(days)
    return Score(
        n=n,
        high_mae=sum(abs(x) for x in dh) / n,
        high_bias=sum(dh) / n,
        low_mae=sum(abs(x) for x in dl) / n,
        low_bias=sum(dl) / n,
    )


def parse_iem_csv(text: str) -> list[tuple[datetime, float]]:
    """IEM's `format=onlycomma` rows as (UTC time, tmpf); blanks skipped."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        v = (row.get("tmpf") or "").strip()
        if not v or v == "M":
            continue
        t = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        out.append((t, float(v)))
    return out


def parse_open_meteo(payload: dict, variable: str) -> list[tuple[datetime, float]]:
    """One hourly variable from an Open-Meteo response as (UTC time, value).

    Requests are made with timezone=GMT so `time` is UTC; nulls (hours a
    model or lead does not cover) are skipped rather than treated as zero."""
    hourly = payload.get("hourly") or {}
    out = []
    for t, v in zip(hourly.get("time", []), hourly.get(variable, []), strict=False):
        if v is None:
            continue
        out.append((datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=UTC), float(v)))
    return out


# --------------------------------------------------------------------------
# Fetching, cached. Throwaway.


def _cached_get(name: str, url: str, params: dict) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists():
        return path.read_text()
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=120)
        except requests.ConnectionError:
            time.sleep(2 ** (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** (attempt + 1))
            continue
        r.raise_for_status()
        path.write_text(r.text)
        return r.text
    raise requests.ConnectionError(f"gave up on {url} after 4 attempts")


def observations(st: Station, start: date, end: date) -> list[tuple[datetime, float]]:
    params = {
        "station": st.sid,
        "data": "tmpf",
        "year1": start.year,
        "month1": start.month,
        "day1": start.day,
        "year2": (end + timedelta(days=1)).year,
        "month2": (end + timedelta(days=1)).month,
        "day2": (end + timedelta(days=1)).day,
        "tz": "Etc/UTC",
        "format": "onlycomma",
        "missing": "empty",
    }
    text = _cached_get(
        f"obs_{st.sid}_{start}_{end}.csv",
        "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py",
        params,
    )
    return parse_iem_csv(text)


def forecasts(st: Station, model: str, start: date, end: date, downscale: bool) -> dict:
    variables = [f"temperature_2m_previous_day{k}" for k in LEADS]
    params = {
        "latitude": st.lat,
        "longitude": st.lon,
        "hourly": ",".join(variables),
        "models": model,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "temperature_unit": "fahrenheit",
        "timezone": "GMT",
    }
    if not downscale:
        params["elevation"] = "nan"
    tag = "dem" if downscale else "grid"
    text = _cached_get(
        f"fc_{st.sid}_{model}_{tag}_{start}_{end}.json",
        "https://previous-runs-api.open-meteo.com/v1/forecast",
        params,
    )
    return json.loads(text)


# --------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    yesterday = date.today() - timedelta(days=1)
    ap.add_argument("--start", type=date.fromisoformat, default=yesterday - timedelta(days=60))
    ap.add_argument("--end", type=date.fromisoformat, default=yesterday)
    args = ap.parse_args()

    print(f"Window {args.start} .. {args.end}; day counted with >= {MIN_HOURS_PER_DAY} hours.\n")
    lead_rows: dict[tuple[str, str, int], list[Score]] = defaultdict(list)

    print("Q1+Q2: day-1 forecast of the daily high / low, error in F (MAE, bias fc-obs)")
    header = f"{'station':6} {'elev':>5} {'model':15} {'grid elev':>9} {'dem elev':>8}"
    header += f" {'n':>3} | {'high raw':>14} {'high corrected':>15} | {'low raw':>14} {'low corrected':>15}"
    print(header)
    for st in STATIONS:
        obs = daily_extremes(observations(st, args.start, args.end), st.utc_offset_s)
        for model in MODELS:
            try:
                raw = forecasts(st, model, args.start, args.end, downscale=False)
                dem = forecasts(st, model, args.start, args.end, downscale=True)
            except requests.HTTPError as e:
                print(f"{st.sid:6} {model:15} unavailable: {e}")
                continue
            off = st.utc_offset_s
            scores = {}
            for tag, payload in (("raw", raw), ("dem", dem)):
                for k in LEADS:
                    fc = daily_extremes(parse_open_meteo(payload, f"temperature_2m_previous_day{k}"), off)
                    s = score(fc, obs)
                    scores[(tag, k)] = s
                    if s:
                        lead_rows[(tag, model, k)].append(s)
            r, d = scores[("raw", 1)], scores[("dem", 1)]
            if not (r and d):
                print(f"{st.sid:6} {st.elev_m:5.0f} {model:15} no overlapping days")
                continue
            print(
                f"{st.sid:6} {st.elev_m:5.0f} {model:15} {raw.get('elevation', float('nan')):9.0f}"
                f" {dem.get('elevation', float('nan')):8.0f} {r.n:3d} |"
                f" {r.high_mae:5.1f} ({r.high_bias:+5.1f})  {d.high_mae:6.1f} ({d.high_bias:+5.1f}) |"
                f" {r.low_mae:5.1f} ({r.low_bias:+5.1f})  {d.low_mae:6.1f} ({d.low_bias:+5.1f})"
            )

    for tag, label in (("raw", "raw grid cell"), ("dem", "corrected to the DEM")):
        print(f"\nQ3: error by lead time, {label}, mean over stations (high MAE / low MAE, F)")
        print(f"{'model':15} " + " ".join(f"{'day ' + str(k):>13}" for k in LEADS))
        for model in MODELS:
            cells = []
            for k in LEADS:
                ss = lead_rows.get((tag, model, k), [])
                if not ss:
                    cells.append(f"{'-':>13}")
                    continue
                h = sum(s.high_mae for s in ss) / len(ss)
                lo = sum(s.low_mae for s in ss) / len(ss)
                cells.append(f"{h:6.1f} / {lo:4.1f}")
            print(f"{model:15} " + " ".join(cells))


if __name__ == "__main__":
    main()
