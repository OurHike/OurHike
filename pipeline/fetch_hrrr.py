"""Download the newest complete 48-hour HRRR run's 2 m temperature (#1056).

The HRRR slice of features/WEATHER.md's build step 1. HRRR supplies the first
two days' temperature, which the phone corrects from each HRRR cell's model
height to a trail point's real height (the maintainer's choice of 2026-09-24,
WEATHER.md §3). This script fetches only the temperature; the cell heights
and land mask are fixed terrain, and `build_weather_squares.py` fetches them
once per data release.

WHICH RUN. HRRR runs every hour, but only the 00, 06, 12 and 18 UTC runs reach
48 hours; the rest stop at 18 (WEATHER.md §2). The job takes the newest of
those four whose 48 forecast hours are all in the bucket, and goes back at
most `MAX_RUNS_BACK` of them. Measured 2026-09-29: the 06Z run's 49 surface
files (hours 0-48) were all present by early afternoon UTC, and the 12Z run
had 3 at the same moment - so the run used is usually 6 to 8 hours old, and
covers about 40 of the next 48 hours (WEATHER.md §3 reasoned the same). The
phone uses HRRR for each hour it covers and NBM after.

WHAT IS DOWNLOADED. One GRIB2 message per forecast hour, `TMP:2 m above
ground`, by byte range from the `.idx` beside each file: 48 messages, 58.5 MB,
in 7.9 s from this sandbox (2026-09-29, the 06Z run). The whole files would be
~6 GB. GDAL reads the message in °C (its GRIB driver converts from the
Kelvin the file stores), and `export_weather.py` refuses a file whose unit tag
says otherwise.

IF THIS FAILS, THE FORECAST STILL PUBLISHES. It removes its own record first
and writes it only on success, so a failed run leaves no `hrrr_cycle.json`,
and `export_weather.py` then publishes NBM alone with `hrrr: null` - the phone
falls back to NBM's uncorrected temperature for every hour, as it will past
hour 48 anyway.

    python fetch_hrrr.py
"""

from __future__ import annotations

import json
import re
import shutil
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from build_weather_squares import grib_message_range
from lib.atomic_write import write_text_atomically
from lib.http_retry import download_with_retry, request_with_retry

ROOT = Path(__file__).resolve().parent
WEATHER_RAW = ROOT / "data" / "raw" / "weather"
HRRR_DIR = WEATHER_RAW / "hrrr"
HRRR_CYCLE_PATH = WEATHER_RAW / "hrrr_cycle.json"

HRRR_BUCKET = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
USER_AGENT = "OurHike (github.com/OurHike/OurHike)"

HOURS = 48
LONG_RUNS = (0, 6, 12, 18)  # the only HRRR runs that reach 48 hours
FIELD, LEVEL = "TMP", "2 m above ground"

# Four long runs is a day. Past that HRRR has stalled for longer than it ever
# should, and its "first two days" would be mostly gone; NBM alone is the
# honest answer, which is what a failure here produces.
MAX_RUNS_BACK = 4

DOWNLOAD_THREADS = 8

SURFACE_FILE = re.compile(r"/hrrr\.t(\d{2})z\.wrfsfcf(\d{2})\.grib2\.idx$")


# --------------------------------------------------------------------------
# Pure pieces - what the tests pin.


def long_runs(now: datetime, back: int = MAX_RUNS_BACK) -> list[datetime]:
    """The newest `back` 48-hour run times at or before `now`, newest first."""
    hour = max(h for h in LONG_RUNS if h <= now.hour)
    latest = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return [latest - timedelta(hours=6 * k) for k in range(back)]


def run_prefix(run: datetime) -> str:
    return f"hrrr.{run:%Y%m%d}/conus/hrrr.t{run:%H}z.wrfsfcf"


def complete(run: datetime, keys: list[str]) -> bool:
    """True when every forecast hour 1..48 of `run` has its index file."""
    hours = set()
    for key in keys:
        match = SURFACE_FILE.search(key)
        if match and int(match[1]) == run.hour:
            hours.add(int(match[2]))
    return all(h in hours for h in range(1, HOURS + 1))


def check_index_hour(index_lines: list[str], start: int, hour: int) -> None:
    """Refuse a message whose own index line is not the forecast hour its
    file name says - a temperature filed under the wrong hour is a plausible
    wrong number."""
    line = next(line for line in index_lines if line.split(":")[1] == str(start))
    expected = f":{hour} hour fcst:"
    if expected not in line:
        raise RuntimeError(f"HRRR index line {line!r} is not forecast hour {hour}")


# --------------------------------------------------------------------------
# The bucket. Network.


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def list_keys(session: requests.Session, prefix: str) -> list[str]:
    keys: list[str] = []
    params = {"list-type": "2", "prefix": prefix}
    while True:
        body = request_with_retry(f"{HRRR_BUCKET}/", session=session, params=params, label=f"list {prefix}").text
        root = ET.fromstring(body)
        keys += [el.text for el in root.iter() if el.tag.endswith("}Key") or el.tag == "Key"]
        token = next((e.text for e in root.iter() if e.tag.endswith("NextContinuationToken")), None)
        if not token:
            return keys
        params["continuation-token"] = token


def find_run(session: requests.Session, now: datetime | None = None) -> datetime:
    for run in long_runs(now or datetime.now(UTC)):
        if complete(run, list_keys(session, run_prefix(run))):
            return run
        print(f"  HRRR {run:%Y-%m-%d %H}Z is not complete yet; trying the one before")
    raise RuntimeError(f"no complete 48-hour HRRR run among the newest {MAX_RUNS_BACK}; HRRR may be stalled")


def download(session: requests.Session, run: datetime) -> dict:
    here = HRRR_DIR / f"{run:%Y%m%dT%H}"
    for old in HRRR_DIR.glob("*") if HRRR_DIR.exists() else []:
        if old != here:
            shutil.rmtree(old)
    here.mkdir(parents=True, exist_ok=True)

    def fetch(hour: int) -> list[str]:
        key = f"{run_prefix(run)}{hour:02d}.grib2"
        index = request_with_retry(f"{HRRR_BUCKET}/{key}.idx", session=session, label=f"HRRR f{hour:02d} idx").text.splitlines()
        start, end = grib_message_range(index, FIELD, LEVEL)
        check_index_hour(index, start, hour)
        dest = here / f"t2m_f{hour:02d}.grb2"
        if not dest.exists():
            download_with_retry(
                f"{HRRR_BUCKET}/{key}",
                dest,
                timeout=120,
                headers={"User-Agent": USER_AGENT, "Range": f"bytes={start}-{end}"},
                label=dest.name,
            )
        valid = run + timedelta(hours=hour)
        return [valid.strftime("%Y-%m-%dT%H:%MZ"), str(dest.relative_to(WEATHER_RAW))]

    with ThreadPoolExecutor(DOWNLOAD_THREADS) as pool:
        files = list(pool.map(fetch, range(1, HOURS + 1)))
    return {"model": "hrrr", "cycle": run.strftime("%Y-%m-%dT%H:%MZ"), "fields": {"temp2m": files}}


def main() -> dict:
    HRRR_CYCLE_PATH.unlink(missing_ok=True)
    session = _session()
    run = find_run(session)
    print(f"Using HRRR {run:%Y-%m-%d %H}Z")
    record = download(session, run)
    write_text_atomically(HRRR_CYCLE_PATH, json.dumps(record, indent=1) + "\n")
    size = sum(p.stat().st_size for p in (HRRR_DIR / f"{run:%Y%m%dT%H}").glob("*.grb2"))
    print(f"Fetched {HOURS} hours of 2 m temperature, {size / 1e6:.1f} MB")
    return record


if __name__ == "__main__":
    main()
