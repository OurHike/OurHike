"""Fetch AT waypoint/POI data from opentrail.org's public API.

Source: https://github.com/austinwritescode/opentrail.org - "Community-driven
trail information resource for thru-hikers." No LICENSE file exists in that
repo; the maintainer reportedly described the data as "open data" in a Reddit
post (r/Ultralight), but that isn't a formal confirmation. See the ROADMAP.md
Phase 1 todo to reach out to the maintainer directly - this fetch proceeds on
that informal basis for now, deliberately excluding user comments (personal
contributions from named individuals - a consent concern separate from and
in addition to the licensing question).

This targets the two gaps confirmed missing from ATC's own data: water
sources and resupply-relevant POIs (icon "w" and "r" below), plus "t" (towns)
as useful resupply context. Icon meanings are inferred from the data, not
documented by the API - treat as best-effort until cross-checked.
"""
import json
from pathlib import Path

import requests

API_URL = "https://opentrail.org/api/getData"
OUT_PATH = Path(__file__).parent / "data" / "raw" / "opentrail_at.geojson"
STATE_PATH = Path(__file__).parent / "data" / "raw" / "opentrail_state.json"

# Best-effort inferred from feature titles/counts - not documented by the API.
ICON_LEGEND = {
    "c": "campsite",
    "s": "shelter (some overlap with 'c' observed in the data)",
    "o": "other / overlook / miscellaneous",
    "j": "junction or road crossing",
    "w": "water source",
    "t": "town",
    "r": "resupply (store/outfitter/service)",
    "a": "unknown (single occurrence)",
}


def fetch_at_data(etag: str | None):
    """Returns (data_or_None, new_etag). data is None if the server confirmed
    nothing changed (304) - the API's own README documents ETag/If-None-Match
    support, so this uses real HTTP conditional requests rather than
    reimplementing change detection client-side."""
    headers = {"If-None-Match": etag} if etag else {}
    resp = requests.get(API_URL, params={"trail": "AT"}, headers=headers, timeout=60)
    if resp.status_code == 304:
        return None, etag
    resp.raise_for_status()
    return resp.json(), resp.headers.get("ETag")


def strip_comments(fc: dict) -> dict:
    """Keep location/POI data; drop user comments per explicit instruction -
    those are personal contributions from named individuals, not ours to
    redistribute without the site's/authors' consent."""
    for feature in fc["features"]:
        props = feature["properties"]
        props.pop("comments", None)
        props.pop("commentCount", None)
    return fc


def main():
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    prior_etag = state.get("etag")

    print(f"Checking {API_URL} ...")
    fc, new_etag = fetch_at_data(prior_etag if OUT_PATH.exists() else None)

    if fc is None:
        print("Up to date (304 Not Modified), skipping.")
        return

    print(f"  {len(fc['features'])} features fetched.")
    fc = strip_comments(fc)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(fc))
    STATE_PATH.write_text(json.dumps({"etag": new_etag}))
    print(f"Saved (comments excluded) -> {OUT_PATH}")

    counts = {}
    for f in fc["features"]:
        icon = f["properties"].get("icon")
        counts[icon] = counts.get(icon, 0) + 1
    print("Icon breakdown (best-effort legend, see ICON_LEGEND in this script):")
    for icon, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {icon} ({ICON_LEGEND.get(icon, 'unknown')}): {count}")


if __name__ == "__main__":
    main()
