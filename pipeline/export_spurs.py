"""Publish what each blue-blazed spur leads to.

The lines already ship. `trails.geojson` carries every side trail, already
blue, already rendered - but the client stores it as an opaque Blob and hands
it straight to MapLibre (client/src/lib/trailData.ts), so it never reads a
single property off it. Enriching that file would put the answer somewhere the
app structurally cannot look.

So this writes a small separate artifact keyed by the trail ids already in
`trails.geojson`:

    {"side_trails:1234": {"name": ..., "length_ft": ...,
                          "destination_poi_id": ..., "destination_distance_m": ...}}

Not a new model - features/SPUR_TRAILS.md is explicit that a spur is a side
trail with `Type=3` and two computed fields, and that introducing a `Spur`
entity would duplicate blaze normalisation, corridor clipping and export
plumbing to express one join. This is that join and nothing else.

RUNS AFTER export_poi.py, and that ordering is load-bearing. The destination
id it publishes has to be the id the client already holds, so it resolves
against export_poi.py's *published* records rather than against the raw ATC
points they were built from. Resolving against the raw points would produce
ids that match nothing on the device - a link to a POI the app cannot find.

The join itself is in lib/spurs.py and is plain Python: 784 spurs against
2,532 POIs is nothing, and keeping it out of DuckDB means the parts most
likely to be wrong - which end is the junction, when to give up - are unit
tested directly.

    .venv/Scripts/python export_spurs.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.arcgis import get_field_coded_domain
from lib.feature_id import resolve_feature_id
from lib.poi_schema import poi_output_name
from lib.spurs import (
    SPUR_TYPE_CODE,
    build_centerline_index,
    build_destination_index,
    decode_type,
    resolve_destination,
)

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
POI_DIR = ROOT / "data" / "processed" / "poi"
OUT_PATH = ROOT / "data" / "processed" / "spurs.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "spurs_manifest.json"
SOURCES_PATH = ROOT / "sources.json"

SIDE_TRAILS_KEY = "side_trails"
CENTERLINE_KEY = "centerline"
TYPE_FIELD = "Type"

# Which POI types may be named as a spur's destination.
#
# features/SPUR_TRAILS.md leaves this deliberately open, and the restraint it
# argues for is worth keeping: a privy is a real destination but a strange
# thing to name as one, and parking is an Access (`Type=0`) concern rather
# than a spur one. These four are the ones a hiker is deciding about when they
# stand at a junction wondering whether the walk is worth it.
DESTINATION_POI_TYPES = ("shelter", "water", "campsite", "resupply")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_features(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return (json.loads(path.read_text()) or {}).get("features") or []


def load_destination_pois(poi_dir: Path | None = None, types=None) -> list[dict]:
    """The published POI records a destination may point at.

    Read from export_poi.py's output rather than from the raw ATC points, so
    that every id published here is an id the client can actually resolve. A
    missing type file is skipped rather than fatal - a partial export is a
    real state this pipeline supports elsewhere, and the honest consequence is
    fewer resolved spurs, not a failed run.

    Defaults arrive via a None sentinel rather than in the signature. A plain
    `=POI_DIR` default binds once at import, so a test pointing the module
    constant somewhere else would find this function still reading the real
    path - the same trap check_freshness.py's topo_sample() documents.
    """
    poi_dir = POI_DIR if poi_dir is None else poi_dir
    types = DESTINATION_POI_TYPES if types is None else types

    pois: list[dict] = []
    for poi_type in types:
        for feature in load_features(poi_dir / poi_output_name(poi_type)):
            properties = feature.get("properties") or {}
            if properties.get("id"):
                pois.append(properties)
    return pois


def source_url(key: str, sources_path: Path | None = None) -> str | None:
    """Where a registered source lives, or None if it is not registered.

    None-sentinel default for the same reason as above.
    """
    sources_path = SOURCES_PATH if sources_path is None else sources_path
    if not sources_path.exists():
        return None
    registry = json.loads(sources_path.read_text()).get("sources") or []
    for source in registry:
        if source.get("key") == key:
            return source.get("url")
    return None


def type_coded_domain(url: str | None) -> dict | None:
    """`Type`'s real coded-value domain from the live FeatureServer.

    A failed lookup is tolerated rather than fatal, matching how fetch_all.py
    already treats a failed `dataLastEditDate` call. lib/spurs.decode_type
    still reads a bare numeric code without a domain, so a bad metadata day
    costs the literal-name decodes rather than every spur in the export.
    """
    if not url:
        return None
    try:
        return get_field_coded_domain(url, TYPE_FIELD)
    except Exception as exc:
        print(f"WARNING: could not read {TYPE_FIELD}'s coded domain ({exc.__class__.__name__})")
        return None


def build_spur_records(
    side_trails: list[dict],
    centerline_features: list[dict],
    pois: list[dict],
    coded_domain: dict | None,
) -> dict[str, dict]:
    """Every `Type=3` side trail, keyed by the id `trails.geojson` uses.

    The id is `{key}:{id}` with the id from lib/feature_id.py's
    resolve_feature_id - the SAME function export_trails.py calls, not a
    reimplementation of it. This docstring used to claim "built the same
    way" over a local copy of the chain, and the copy had already drifted
    (truthiness for `is None`, OBJECTID for the feature's own id), which
    made any feature off the happy path silently fail the join this
    artifact exists for.
    """
    centerline = build_centerline_index(centerline_features)
    destinations = build_destination_index(pois)

    records: dict[str, dict] = {}
    undecodable = 0

    for index, feature in enumerate(side_trails):
        properties = feature.get("properties") or {}
        raw_type = properties.get(TYPE_FIELD)
        code = decode_type(raw_type, coded_domain)

        if code is None and raw_type is not None and str(raw_type).strip():
            undecodable += 1
        if code != SPUR_TYPE_CODE:
            continue

        feature_id = resolve_feature_id(SIDE_TRAILS_KEY, feature, properties, index)
        geometry = feature.get("geometry") or {}
        resolved = resolve_destination(geometry.get("coordinates") or [], centerline, destinations)

        records[f"{SIDE_TRAILS_KEY}:{feature_id}"] = {
            "name": properties.get("Name"),
            # ATC's own GNSS measurement, not recomputed from the geometry.
            # They surveyed it; recomputing would be a worse number arrived at
            # with more work.
            "length_ft": properties.get("Length_Ft"),
            **resolved,
        }

    if undecodable:
        # Loud, never silent - the same convention fetch_topo_quads.py and
        # export_trails.py already follow. A side trail whose Type does not
        # decode is not a spur as far as this runs is concerned, and that is
        # worth saying out loud rather than discovering as a count that moved.
        print(f"WARNING: {undecodable} side trail(s) have an undecodable {TYPE_FIELD} - not treated as spurs")

    return records


def main() -> dict:
    side_trails = load_features(RAW_DIR / "side_trails.geojson")
    centerline_features = load_features(RAW_DIR / "centerline.geojson")
    pois = load_destination_pois()

    if not side_trails:
        print("No side_trails.geojson - run fetch_all.py first.")
        return {}
    if not centerline_features:
        print("No centerline.geojson - run fetch_all.py first.")
        return {}
    if not pois:
        # Not fatal, and not silent. Every spur would resolve to no
        # destination, which looks exactly like a trail network where nothing
        # leads anywhere - a result worth refusing to publish quietly.
        #
        # It says what it looked for and what is actually there, because the
        # earlier version said only "run export_poi.py first" and that was
        # false: export_poi.py HAD run, one step earlier and green, and the
        # files it wrote were sitting in this directory under names this
        # function was not asking for (#469). A reader who trusts the advice
        # checks the workflow ordering, finds it correct, and stops - so the
        # guard meant to expose the fault was the thing concealing it. A
        # warning that names both sides cannot mislead that way.
        print(f"WARNING: no published POIs found under {POI_DIR} - run export_poi.py first.")
        print(f"  looked for: {', '.join(poi_output_name(t) for t in DESTINATION_POI_TYPES)}")
        found = sorted(p.name for p in POI_DIR.glob("*.geojson")) if POI_DIR.is_dir() else []
        print(f"  found: {', '.join(found) if found else '(nothing - directory is empty or absent)'}")

    coded_domain = type_coded_domain(source_url(SIDE_TRAILS_KEY))
    records = build_spur_records(side_trails, centerline_features, pois, coded_domain)

    resolved = sum(1 for r in records.values() if r["destination_poi_id"])
    print(f"{len(records)} spurs, {resolved} with a destination ({resolved / len(records):.0%})" if records else "0 spurs")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records, separators=(",", ":"), sort_keys=True))

    manifest = {
        "path": str(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "spur_count": len(records),
        "resolved_count": resolved,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"Spurs -> {OUT_PATH}\nManifest -> {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    main()
