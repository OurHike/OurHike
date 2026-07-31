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

from lib.completeness import fail_if_incomplete

API_URL = "https://opentrail.org/api/getData"
OUT_PATH = Path(__file__).parent / "data" / "raw" / "opentrail_at.geojson"
STATE_PATH = Path(__file__).parent / "data" / "raw" / "opentrail_state.json"

# A well-formed-but-empty or drastically-shrunk API response must not
# silently overwrite good local data and get its ETag persisted - a later
# run would otherwise see 304 Not Modified against that *new* (bad) ETag and
# treat the degraded state as confirmed-current forever, with no recovery
# path short of a human noticing and deleting STATE_PATH by hand. 50% is a
# deliberately loose threshold: normal upstream editing (a handful of POIs
# added, removed, or re-tagged between runs) should never lose half the
# dataset, so a drop past this line reads as "something's structurally
# broken" (bad filter, auth failure returning an empty-but-valid body, API
# response shape change) rather than routine community editing.
MAX_FEATURE_DROP_RATIO = 0.5

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


def regression_problems(new_count: int, prior_out_path: Path) -> list[str]:
    """Problem strings (suitable for lib.completeness.fail_if_incomplete) if
    `new_count` looks like a broken fetch relative to whatever's already on
    disk at `prior_out_path` - see MAX_FEATURE_DROP_RATIO's comment for why.
    A prior file that doesn't exist yet, isn't parseable, or itself has zero
    features means there's nothing on-disk worth protecting, so nothing is
    flagged in that case - this only guards an existing good state."""
    if not prior_out_path.exists():
        return []
    try:
        prior_count = len(json.loads(prior_out_path.read_text())["features"])
    except (json.JSONDecodeError, KeyError):
        return []
    if prior_count == 0:
        return []

    if new_count == 0:
        return [f"opentrail fetch returned 0 features (previously {prior_count}) - refusing to overwrite {prior_out_path}"]
    if new_count < prior_count * (1 - MAX_FEATURE_DROP_RATIO):
        drop_ratio = 1 - new_count / prior_count
        return [
            f"opentrail fetch returned {new_count} features, down from {prior_count} "
            f"({drop_ratio:.0%} drop, over the {MAX_FEATURE_DROP_RATIO:.0%} threshold) "
            f"- refusing to overwrite {prior_out_path}"
        ]
    return []


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

    # Guard against persisting a degraded response (and its ETag) over good
    # local data - see MAX_FEATURE_DROP_RATIO / regression_problems above.
    # Must run before either write below: on refusal, OUT_PATH and
    # STATE_PATH both need to stay exactly as they were so next run's
    # ETag-based skip logic keeps comparing against the last known-good
    # state instead of a newly-persisted bad one.
    fail_if_incomplete(regression_problems(len(fc["features"]), OUT_PATH), label="Refusing to persist opentrail fetch")

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
