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
directory, so the boundary between the A.T. build and everyone else's
layers is visible on disk. The fetch is change-aware the way fetch_all.py's
is, with one more marker (#1311): each layer's change marker is compared
against the one recorded in data/raw/external/manifest.json, and an
unchanged layer whose output still exists is skipped rather than
re-fetched. The marker is, in order of preference:

  - editingInfo.dataLastEditDate, one cheap metadata request (verified live
    on all four OPRHP layers 2026-08-18) - every AGOL-hosted layer has it;
  - the substitute sources.json records for a layer whose server has no
    editingInfo: `freshness.kind: arcgis_max_field` (a max() statistics
    query on a date column - NYS DEC's on-prem MapServer) or
    `freshness.marker: etag` (a HEAD on the service description - the
    Forest Service's EDW server, which has no date column either);
  - nothing, for a layer whose entry declares `marker: none` (NH GRANIT),
    which is fetched every run and says so.

WHY THE SUBSTITUTES EXIST. Measured 2026-09-08 on run #88 of the publish
(#1311): all 18 layers were fetched on every run - ~195,000 features over
~200 sequential page requests, 9m43s to 12m51s, byte-identical output run
to run. Eleven of the eighteen have no editingInfo, so the skip above could
never fire for them; and data/raw/external/ was not in the publish
workflow's cache list, so the manifest the other seven compare against
never survived a runner either. The registry had carried the substitute
markers since 2026-08-27 with the note "nothing reads this block yet".
This reads it. Whether the Forest Service's metadata ETag moves when its
FEATURES move is still @unvalidated - the manifest records both sides of
every comparison so the answer accumulates in the log rather than being
assumed.

THE FILES THIS WRITES ARE READ. This docstring used to say nothing
downstream read them, which was true while every steward was review-only;
since 2026-08-24 export_nearby_trails.py, export_nearby_poi.py,
load_raw.py and, through the network file, the corridor, the water gate
and the junction graph all do. It still writes no fetch receipt: receipts
are check_output_quality.py's contract with the REQUIRED fetchers, this
one runs `continue-on-error` because another organization's outage must
not fail an A.T. publish, and a receipt restored without its outputs reads
as drift on the gate in front of publish - a false alarm in the worst place.
"""

import json
from pathlib import Path

from lib.arcgis import fetch_layer_to_file, get_layer_edit_date, get_layer_max_field, get_service_etag
from lib.completeness import count_problems, fail_if_incomplete
from lib.source_registry import external_arcgis_sources, load_registry

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
RAW_DIR = ROOT / "data" / "raw" / "external"
MANIFEST_PATH = RAW_DIR / "manifest.json"

# The marker kinds a manifest entry can carry, spelled once. `data_last_edit_date`
# is the one every entry always had; the other two are the substitutes
# (#1311) and name the registry block they came from.
EDIT_DATE_MARKER = "data_last_edit_date"
ETAG_MARKER = "etag"
MAX_FIELD_MARKER = "max_field"


def current_marker(src: dict) -> tuple[dict | None, str]:
    """This run's change marker for one layer, and a phrase saying which.

    `({"kind": ..., "value": ...}, "editingInfo")` when the server or the
    registry offers something to compare; `(None, reason)` when nothing can
    be had, which the caller reads as "fetch" - never as "unchanged".
    Preference order is the module docstring's. A marker read that fails
    is reported and treated as absent rather than raised, because a flaky
    metadata endpoint must cost a re-fetch and never the run.
    """
    try:
        edit_date = get_layer_edit_date(src["url"])
    except Exception as error:  # noqa: BLE001 - reported, then fetched
        return None, f"couldn't check editingInfo ({error})"
    if edit_date is not None:
        return {"kind": EDIT_DATE_MARKER, "value": str(edit_date)}, "editingInfo"

    freshness = src.get("freshness") or {}
    if freshness.get("kind") == "arcgis_max_field" and freshness.get("field"):
        field = freshness["field"]
        try:
            value = get_layer_max_field(src["url"], field)
        except Exception as error:  # noqa: BLE001 - same posture as above
            return None, f"no editingInfo, and max({field}) could not be read ({error})"
        if value is None:
            return None, f"no editingInfo, and max({field}) came back empty"
        return {"kind": MAX_FIELD_MARKER, "field": field, "value": value}, f"max({field})"

    if freshness.get("marker") == "etag" and freshness.get("url"):
        try:
            value = get_service_etag(freshness["url"])
        except Exception as error:  # noqa: BLE001 - same posture as above
            return None, f"no editingInfo, and the service ETag could not be read ({error})"
        if value is None:
            return None, "no editingInfo, and the service answered no ETag"
        return {"kind": ETAG_MARKER, "url": freshness["url"], "value": value}, "service ETag"

    return None, "no editingInfo and no substitute marker registered"


def recorded_marker(prior: dict | None) -> dict | None:
    """The marker the last fetch recorded, reading a manifest written before
    markers had a `kind` as the edit-date marker it was."""
    if not prior:
        return None
    if prior.get("marker") is not None:
        return prior["marker"]
    if prior.get(EDIT_DATE_MARKER) is not None:
        return {"kind": EDIT_DATE_MARKER, "value": str(prior[EDIT_DATE_MARKER])}
    return None


def main():
    registry = load_registry(SOURCES_PATH)
    sources = external_arcgis_sources(registry)
    prior_manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}

    results = {}
    skipped = 0
    for src in sources:
        key = src["key"]
        out_path = RAW_DIR / f"{key}.geojson"
        prior = prior_manifest.get(key)

        marker, described = current_marker(src)
        if marker is not None and recorded_marker(prior) == marker and out_path.exists():
            print(f"{src['title']} ({key}): up to date ({described} unchanged), skipping")
            results[key] = prior
            skipped += 1
            continue

        why = f"{described} moved" if marker is not None and prior else described
        print(f"Fetching {src['title']} ({key}) from {src['url']} ({why}) ...")
        try:
            count = fetch_layer_to_file(src["url"], out_path)
            print(f"  -> {count} features -> {out_path}")
            results[key] = {
                "title": src["title"],
                "url": src["url"],
                "feature_count": count,
                # Kept under its old name for every reader of the manifest
                # that predates `marker`; None when the server has none.
                "data_last_edit_date": int(marker["value"]) if marker and marker["kind"] == EDIT_DATE_MARKER else None,
                "marker": marker,
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
    # Counted, because "all up to date" used to be printed whether or not a
    # single layer had been skipped (#1311) - the number is the finding.
    print(f"\n{len(sources)} external layers: {len(sources) - skipped} fetched, {skipped} unchanged. Manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
