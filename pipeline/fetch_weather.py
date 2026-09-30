"""Download the newest complete NBM forecast cycle the weather card needs (#1056).

NOAA's National Blend of Models, from its Cloud-Optimized GeoTIFF bucket on
AWS open data (`noaa-nbm-pds`), for the reasons features/WEATHER.md §2 gives:
the only kind of source that serves ~74,000 squares an hour without a quota,
under NOAA's open-data terms. The maintainer chose NBM over NDFD on
2026-09-24, and the GeoTIFFs over GRIB2 because each field is one small file
(~0.7 MB for the whole of CONUS) that GDAL reads without a GRIB decoder - and
so without the half-mirrored-rows trap GRIB decoding sets (WEATHER.md §6).

WHAT IS FETCHED, AND WHY THESE
------------------------------
The card's three frames (WEATHER.md §5) need an hour-by-hour strip, five days
of highs and lows, and the chance of rain and storms:

    hourly, hours 1-48   temp (F), pop01 (%), sky (%), windspd, windgust (kt)
    hourly, hours 1-36   tstm01 (%) - NBM's one-hour thunder probability
                         stops at 36 hours; nothing is padded past it
    periods, 7 days      maxt, mint (F), pop12 (%)

Each period file is named by the time its window ENDS - 06Z for maxt, 18Z for
mint, every six hours for pop12. pop12's own GRIB tag says "12 hr Prob of
Precip > 0.01 In."; the maxt and mint files carry no tags at all (read
2026-09-25), so how long their windows are is not claimed here, and the
published file says only where each one ends.

Units are NBM's own and stay so: store what the source says, convert at
display (CONTRIBUTING.md). The GeoTIFFs carry integers in NWS units - checked
against the GRIB2 edition at seven points on 2026-09-24 and equal to within
rounding - and wind has no unit tag in the file, so `kt` is that measurement
rather than something the file states.

A CYCLE IS USED ONLY WHEN IT IS COMPLETE. Cycles land 36 minutes to about two
hours after their nominal hour (measured over 48 cycles, 2026-09-23/24), and
one was still missing at 90 minutes. A half-written cycle would publish a
card whose later hours are silently another run's - so the job walks back
from the newest cycle to the first one holding every file above, and refuses
to go back further than `MAX_CYCLES_BACK`.

    python fetch_weather.py
"""

from __future__ import annotations

import json
import re
import shutil
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from lib.atomic_write import write_text_atomically
from lib.http_retry import download_with_retry, request_with_retry

ROOT = Path(__file__).resolve().parent
WEATHER_RAW = ROOT / "data" / "raw" / "weather"
NBM_DIR = WEATHER_RAW / "nbm"
CYCLE_PATH = WEATHER_RAW / "cycle.json"

NBM_BUCKET = "https://noaa-nbm-pds.s3.amazonaws.com"
USER_AGENT = "OurHike (github.com/OurHike/OurHike)"
REGION = "conus"

# field -> how many hourly steps the card uses, counted from the cycle hour.
HOURLY = {"temp": 48, "pop01": 48, "sky": 48, "windspd": 48, "windgust": 48, "tstm01": 36}

# Fields published as windows rather than hours, kept to the card's week.
PERIODS = ("maxt", "mint", "pop12")
PERIOD_HORIZON_HOURS = 7 * 24

# Six cycles is six hours. Past that the newest complete forecast is older
# than GitHub's measured ~4-hour clock (#1346) would ever explain, and
# publishing it would be publishing a stall as if it were news.
MAX_CYCLES_BACK = 6

DOWNLOAD_THREADS = 8

VERSION_PREFIX = re.compile(r"^blendv(\d+)\.(\d+)/$")
FILE_TIMES = re.compile(r"_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\.tif$")


@dataclass(frozen=True)
class Cycle:
    version: str  # "blendv5.0"
    time: datetime  # the run's nominal hour, UTC

    @property
    def prefix(self) -> str:
        return f"{self.version}/{REGION}/{self.time:%Y/%m/%d/%H}00/"

    @property
    def stamp(self) -> str:
        return f"{self.time:%Y%m%dT%H}"


# --------------------------------------------------------------------------
# Pure pieces - what the tests pin.


def newest_version(prefixes: list[str]) -> str:
    """The highest `blendvX.Y` among the bucket's top-level prefixes."""
    versions = [(int(m[1]), int(m[2]), p.rstrip("/")) for p in prefixes if (m := VERSION_PREFIX.match(p))]
    if not versions:
        raise RuntimeError(f"no blendvX.Y prefix at the bucket root (saw {prefixes[:5]})")
    return max(versions)[2]


def cycle_times(prefixes: list[str]) -> list[datetime]:
    """Cycle hours from `.../YYYY/MM/DD/HH00/` prefixes, newest first."""
    times = []
    for prefix in prefixes:
        match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/(\d{2})00/$", prefix)
        if match:
            times.append(datetime(*map(int, match.groups()), tzinfo=UTC))
    return sorted(times, reverse=True)


def valid_time(key: str) -> datetime | None:
    match = FILE_TIMES.search(key)
    if not match:
        return None
    return datetime.strptime(match[2], "%Y-%m-%dT%H:%M").replace(tzinfo=UTC)


def needed(cycle: datetime, listings: dict[str, list[str]]) -> dict[str, list[tuple[datetime, str]]] | None:
    """{field: [(valid time, key), ...]} for a cycle, or None if the cycle is
    missing anything the card needs. `listings` is every key under each
    field's prefix."""
    chosen: dict[str, list[tuple[datetime, str]]] = {}
    for field, hours in HOURLY.items():
        by_time = {t: k for k in listings.get(field, []) if (t := valid_time(k))}
        wanted = [cycle + timedelta(hours=h) for h in range(1, hours + 1)]
        if any(t not in by_time for t in wanted):
            return None
        chosen[field] = [(t, by_time[t]) for t in wanted]
    horizon = cycle + timedelta(hours=PERIOD_HORIZON_HOURS)
    for field in PERIODS:
        within = sorted((t, k) for k in listings.get(field, []) if (t := valid_time(k)) and cycle < t <= horizon)
        if not within:
            return None
        chosen[field] = within
    return chosen


# --------------------------------------------------------------------------
# The bucket. Network.


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def list_bucket(session: requests.Session, prefix: str, delimiter: str | None = None) -> tuple[list[str], list[str]]:
    """(keys, common prefixes) under `prefix`, following continuation tokens."""
    keys: list[str] = []
    prefixes: list[str] = []
    params = {"list-type": "2", "prefix": prefix}
    if delimiter:
        params["delimiter"] = delimiter
    while True:
        body = request_with_retry(f"{NBM_BUCKET}/", session=session, params=params, label=f"list {prefix}").text
        root = ET.fromstring(body)
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "Key":
                keys.append(element.text)
            elif tag == "Prefix" and element.text and element.text != prefix:
                prefixes.append(element.text)
        token = next((e.text for e in root.iter() if e.tag.endswith("NextContinuationToken")), None)
        if not token:
            return keys, prefixes
        params["continuation-token"] = token


def find_cycle(session: requests.Session, now: datetime | None = None) -> tuple[Cycle, dict]:
    now = now or datetime.now(UTC)
    _, roots = list_bucket(session, "", delimiter="/")
    version = newest_version(roots)
    candidates: list[datetime] = []
    for back in (0, 1):
        day = now - timedelta(days=back)
        _, found = list_bucket(session, f"{version}/{REGION}/{day:%Y/%m/%d}/", delimiter="/")
        candidates.extend(cycle_times(found))
    for cycle_time in sorted(set(candidates), reverse=True)[:MAX_CYCLES_BACK]:
        cycle = Cycle(version, cycle_time)
        listings = {field: list_bucket(session, f"{cycle.prefix}{field}/")[0] for field in (*HOURLY, *PERIODS)}
        chosen = needed(cycle_time, listings)
        if chosen is not None:
            return cycle, chosen
        print(f"  {cycle.prefix} is not complete yet; trying the one before")
    raise RuntimeError(f"no complete {version} cycle among the newest {MAX_CYCLES_BACK}; NBM may be stalled")


def download(cycle: Cycle, chosen: dict[str, list[tuple[datetime, str]]]) -> dict:
    """Fetch every chosen file into data/raw/weather/nbm/<cycle>/ and return
    the record export_weather.py reads."""
    here = NBM_DIR / cycle.stamp
    for old in NBM_DIR.glob("*") if NBM_DIR.exists() else []:
        if old != here:
            shutil.rmtree(old)
    jobs = []
    record: dict[str, list[list[str]]] = {}
    for field, files in chosen.items():
        record[field] = []
        for when, key in files:
            dest = here / field / key.rsplit("/", 1)[-1]
            record[field].append([when.strftime("%Y-%m-%dT%H:%MZ"), str(dest.relative_to(WEATHER_RAW))])
            if not dest.exists():
                jobs.append((f"{NBM_BUCKET}/{key}", dest))

    def fetch(job):
        url, dest = job
        dest.parent.mkdir(parents=True, exist_ok=True)
        download_with_retry(url, dest, timeout=120, headers={"User-Agent": USER_AGENT}, label=dest.name)

    with ThreadPoolExecutor(DOWNLOAD_THREADS) as pool:
        list(pool.map(fetch, jobs))
    return {"version": cycle.version, "cycle": cycle.time.strftime("%Y-%m-%dT%H:%MZ"), "fields": record}


def main() -> dict:
    session = _session()
    cycle, chosen = find_cycle(session)
    files = sum(len(v) for v in chosen.values())
    print(f"Using {cycle.prefix}: {files} files across {len(chosen)} fields")
    record = download(cycle, chosen)
    write_text_atomically(CYCLE_PATH, json.dumps(record, indent=1) + "\n")
    size = sum(p.stat().st_size for p in (NBM_DIR / cycle.stamp).rglob("*.tif"))
    print(f"Fetched {files} files, {size / 1e6:.1f} MB, into {NBM_DIR / cycle.stamp}")
    return record


if __name__ == "__main__":
    main()
