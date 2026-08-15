"""Fetch one week's U.S. Drought Monitor polygons (#720).

[WATER_CONDITIONS.md](WATER_CONDITIONS.md) §4 is the survey this comes from,
and the reason this source is the first of its three to be built: it is the
only one that says "this region is running dry" without implying anything
about a particular spring, which is the claim the data can actually support.

WHY THE DATED FILE AND NOT `usdm_current.json`
----------------------------------------------
NDMC publishes both. `usdm_current.json` is the same bytes as whichever dated
file is newest - measured 2026-08-15, both were 27,606,546 bytes - but it
carries no date *inside* it: its features hold `OBJECTID`, `DM`,
`Shape_Length` and `Shape_Area`, and nothing else. A weekly product whose
artifact cannot say which week it is would leave the client with only the
bake's own clock, which is the "fresh bytes carrying a stale claim" failure
`export_atc_updates.py` documents at length.

Fetching `usdm_YYYYMMDD.json` for an explicit Tuesday fixes that: the date is
an input rather than something to be inferred, the fetch is reproducible, and
the artifact can name the week it describes.

THE RELEASE RHYTHM, WHICH IS WHY THIS WALKS BACKWARDS
-----------------------------------------------------
A USDM week runs Tuesday to Monday and is *released* on the Thursday. So on a
Tuesday or Wednesday the current week's file does not exist yet, and asking
for it returns a 404 that means "not published yet", not "broken". This walks
back a week at a time until a file answers, which makes the normal midweek
case ordinary rather than an error path - and caps the walk, because a
fetcher that would try a hundred weeks on a bad host is a fetcher that hangs.

LICENCE
-------
Recorded in `sources.json` under `usdm_licence`, on the maintainer's
declaration of 2026-08-15. NDMC's permission page asks for a specific credit
naming all four partners; `client/src/map/credits.ts` carries it, and the
registry entry holds the wording so the two cannot drift.

    python fetch_drought.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from lib import fetch_receipts

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "raw" / "drought"

USDM_DATED = "https://droughtmonitor.unl.edu/data/json/usdm_{stamp}.json"

# A USDM week is stamped with its Tuesday.
RELEASE_WEEKDAY = 1  # Monday is 0

# How many weeks back to look before giving up. Three covers the honest cases
# - a midweek run before Thursday's release, and a release that slipped - and
# stops well short of quietly publishing month-old drought as current.
MAX_WEEKS_BACK = 3

# Anything much smaller than this is not the national polygon set. Measured
# 2026-08-15: the 2026-08-11 release is 27.6 MB and the 2026-08-04 one 26.7 MB.
# The floor is deliberately far below both - it is here to catch an error page
# served with a 200, not to police week-to-week variation.
MIN_PLAUSIBLE_BYTES = 1_000_000


def release_stamp_for(today: date) -> date:
    """The Tuesday of the week `today` falls in, which is that week's stamp."""
    return today - timedelta(days=(today.weekday() - RELEASE_WEEKDAY) % 7)


def candidate_stamps(today: date) -> list[date]:
    first = release_stamp_for(today)
    return [first - timedelta(weeks=back) for back in range(MAX_WEEKS_BACK + 1)]


def fetch_release(stamp: date) -> dict | None:
    """One week's polygons, or None if NDMC has not published that week."""
    url = USDM_DATED.format(stamp=stamp.strftime("%Y%m%d"))
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    if len(raw) < MIN_PLAUSIBLE_BYTES:
        raise SystemExit(
            f"{url} answered {len(raw)} bytes, under the {MIN_PLAUSIBLE_BYTES} floor. "
            "That is an error page or a truncated response, not a week of drought "
            "polygons, and publishing it would draw a map of nothing."
        )
    document = json.loads(raw)
    features = document.get("features")
    if not isinstance(features, list) or not features:
        raise SystemExit(f"{url} parsed but holds no features, so there is nothing to clip.")
    return document


def main(today: date | None = None) -> Path | None:
    today = today or date.today()
    for stamp in candidate_stamps(today):
        document = fetch_release(stamp)
        if document is None:
            print(f"  {stamp:%Y-%m-%d}: not published yet")
            continue
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"usdm_{stamp:%Y%m%d}.json"
        partial = out_path.with_suffix(".json.partial")
        partial.write_text(json.dumps(document))
        partial.replace(out_path)
        classes = sorted({feature["properties"]["DM"] for feature in document["features"]})
        print(f"Wrote {out_path} - {len(document['features'])} features, classes {classes}.")
        fetch_receipts.record("fetch_drought", [out_path])
        return out_path

    raise SystemExit(
        f"No U.S. Drought Monitor release found in the last {MAX_WEEKS_BACK + 1} weeks "
        f"(tried {', '.join(f'{s:%Y-%m-%d}' for s in candidate_stamps(today))}). "
        "Publishing nothing rather than something older: a drought map is a claim "
        "about this week."
    )


if __name__ == "__main__":
    main()
