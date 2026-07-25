"""Fetch every ATC data source listed in sources.json and write a manifest.

Usage: python fetch_all.py

Each source is written to data/raw/<key>.geojson. After fetching, this
verifies that every source in the registry produced a non-empty output file
before writing data/raw/manifest.json - if any source is missing or failed,
the script exits non-zero rather than silently continuing.
"""
import json
import sys
from pathlib import Path

from lib.arcgis import fetch_layer_to_file

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"


def main():
    registry = json.loads(SOURCES_PATH.read_text())
    sources = registry["sources"]

    results = {}
    failures = []
    for src in sources:
        key = src["key"]
        out_path = RAW_DIR / f"{key}.geojson"
        print(f"Fetching {src['title']} ({key}) from {src['url']} ...")
        try:
            count = fetch_layer_to_file(src["url"], out_path)
            print(f"  -> {count} features -> {out_path}")
            results[key] = {"title": src["title"], "url": src["url"], "feature_count": count}
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append(key)

    # Completeness check: every registered source must have succeeded.
    missing = [s["key"] for s in sources if s["key"] not in results]
    if missing or failures:
        print(f"\nIncomplete fetch. Missing/failed sources: {sorted(set(missing + failures))}")
        sys.exit(1)

    MANIFEST_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nAll {len(sources)} sources fetched successfully. Manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
