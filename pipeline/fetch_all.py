"""Fetch every ATC feature layer listed in sources.json and write a manifest.

Usage: python fetch_all.py

**Every ArcGIS feature layer, not every source.** sources.json has held one
kind of thing since it was written, and now holds two: ATC's Trail Updates
are published as prose on a website rather than as a data layer
(features/ATC_TRAIL_UPDATES.md, #459), so there is no layer here to query and
no `data/raw/<key>.geojson` for one to produce. lib/source_registry.py owns
that distinction; this script asks it rather than reading `kind` itself.

Skipping is not a courtesy to the other source - it is what keeps the
completeness gate below meaningful. A non-layer entry left in this loop would
fail its metadata check, fetch nothing, and land in `counts` as 0 features,
which is exactly the signal that gate exists to treat as a broken run. The
gate would then be red on every single run, for a source that was never
supposed to be here, and a gate that is always red is one nobody reads.

Each fetched source is written to data/raw/<key>.geojson. Before doing the full
(potentially paginated, slower) feature fetch, this checks each layer's
dataLastEditDate (a cheap metadata-only request) against the last value
recorded in the manifest - if unchanged and the output file still exists,
the source is skipped rather than re-fetched. This is what makes running
this on a schedule (e.g. weekly, see ROADMAP.md Phase 1) cheap: most weeks
nothing has changed upstream, so most runs do ~9 small metadata checks and
no actual data transfer.

After fetching, this verifies that every source in the registry produced a
non-empty feature collection before writing data/raw/manifest.json - not
just that a fetch was attempted. An ArcGIS FeatureServer query error can
come back as HTTP 200 with an empty features array rather than a non-2xx
status (lib/arcgis.py's fetch_layer_geojson() has no floor for this), which
would otherwise be recorded as an ordinary successful fetch with
feature_count 0. If any source is missing, failed, or comes back with
feature_count 0, the script exits non-zero rather than silently continuing.
"""

import json
from pathlib import Path

from lib.arcgis import fetch_layer_to_file, get_layer_edit_date
from lib.completeness import count_problems, fail_if_incomplete
from lib.source_registry import arcgis_sources, load_registry

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"


def main():
    registry = load_registry(SOURCES_PATH)
    sources = arcgis_sources(registry)
    prior_manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}

    results = {}
    for src in sources:
        key = src["key"]
        out_path = RAW_DIR / f"{key}.geojson"
        prior = prior_manifest.get(key)

        edit_date = None
        try:
            edit_date = get_layer_edit_date(src["url"])
        except Exception as e:
            print(f"  {key}: couldn't check edit date ({e}), will fetch anyway")

        if edit_date is not None and prior and prior.get("data_last_edit_date") == edit_date and out_path.exists():
            print(f"{src['title']} ({key}): up to date (unchanged since last fetch), skipping")
            results[key] = prior
            continue

        print(f"Fetching {src['title']} ({key}) from {src['url']} ...")
        try:
            count = fetch_layer_to_file(src["url"], out_path)
            print(f"  -> {count} features -> {out_path}")
            results[key] = {
                "title": src["title"],
                "url": src["url"],
                "feature_count": count,
                "data_last_edit_date": edit_date,
            }
        except Exception as e:
            print(f"  FAILED: {e}")

    # Completeness check: every registered source must have produced a
    # non-empty feature collection, not merely an entry in `results` - a
    # source missing entirely (never attempted, or caught by the except
    # above) and a source that "succeeded" with feature_count 0 (see the
    # module docstring) are both a count of 0 here, so neither can slip a
    # manifest.json that looks authoritative but isn't. Runs before the
    # manifest is written, matching the "incomplete run leaves no artifact
    # that looks authoritative" pattern this project uses elsewhere.
    counts = {src["key"]: results.get(src["key"], {}).get("feature_count", 0) for src in sources}
    fail_if_incomplete(count_problems(counts), label="Incomplete fetch")

    MANIFEST_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nAll {len(sources)} feature layers up to date. Manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
