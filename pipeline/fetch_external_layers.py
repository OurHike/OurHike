"""Fetch every external-organization ArcGIS layer in sources.json, for review.

Usage: python fetch_external_layers.py

**The entries this fetches are `kind: "external_arcgis_layer"`** - feature
layers on another organization's own ArcGIS org, outside the A.T. build.
NYS OPRHP's four Parks Explorer layers are the first occupants (#769, filed
by #768's program). lib/source_registry.py owns the kind; this script asks
it rather than reading `kind` itself, the same split fetch_all.py uses.

A separate script rather than a widened fetch_all.py, for two reasons that
are both about that script's completeness gate:

- fetch_all.py's gate is the A.T. release's - "every registered source
  produced a non-empty collection, or the run failed". Folding another
  organization's layers into that loop couples the A.T. fetch to that org's
  uptime, so an OPRHP outage would fail an A.T. data release that never
  reads OPRHP bytes.
- One of these layers is a TEMPORARY trail-closure layer whose honest
  feature count in a good week is zero. Under a non-empty gate that reads
  as a broken run, every good week, and a gate that is always red is one
  nobody reads. Entries may declare `may_be_empty: true`, and this script's
  gate lets exactly those come back empty (an ArcGIS query error can still
  arrive as HTTP 200 with an empty features array - lib/arcgis.py has no
  floor for it - so the allowance is per-entry and deliberate, never the
  default).

Each fetched source is written to data/raw/external/<key>.geojson - its own
directory, so the review-only boundary is visible on disk. The fetch is
change-aware exactly the way fetch_all.py's is: each layer's
editingInfo.dataLastEditDate (one cheap metadata request, verified live on
all four OPRHP layers 2026-08-18) is compared against the value recorded in
data/raw/external/manifest.json, and an unchanged layer whose output still
exists is skipped rather than re-fetched.

**Nothing downstream reads these files yet, and that is the point.** The
oprhp_licence block in sources.json records terms as pending the
maintainer's own outreach; until its answer lands, this data is for review
and the #771 spike only (CONTRIBUTING.md, "A note on data and licences").
For the same reason this script writes no fetch receipt: receipts exist so
the publish workflow can re-check cached bytes (#542), no publish workflow
runs this fetcher, and a receipt restored without cached outputs reads as
drift on the gate in front of publish - a false alarm in the worst place.
"""

import json
from pathlib import Path

from lib.arcgis import fetch_layer_to_file, get_layer_edit_date
from lib.completeness import count_problems, fail_if_incomplete
from lib.source_registry import external_arcgis_sources, load_registry

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
RAW_DIR = ROOT / "data" / "raw" / "external"
MANIFEST_PATH = RAW_DIR / "manifest.json"


def main():
    registry = load_registry(SOURCES_PATH)
    sources = external_arcgis_sources(registry)
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

    # fetch_all.py's completeness gate, with one deliberate difference: an
    # entry declaring `may_be_empty: true` is allowed a zero-feature result,
    # because for a temporary-closures layer zero is a fact about the parks
    # rather than a broken fetch. A source missing entirely (never attempted,
    # or caught by the except above) still fails regardless of the flag.
    counts = {src["key"]: results.get(src["key"], {}).get("feature_count", 0) for src in sources}
    minimums = {src["key"]: 0 for src in sources if src.get("may_be_empty") and src["key"] in results}
    fail_if_incomplete(count_problems(counts, minimums=minimums), label="Incomplete fetch")

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nAll {len(sources)} external layers up to date. Manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
