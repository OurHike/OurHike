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

import json
from pathlib import Path

from lib.arcgis import get_field_coded_domain
from lib.completeness import fail_if_incomplete
from lib.feature_id import resolve_feature_id
from lib.hashing import sha256_file
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
# than a spur one. These are the ones a hiker is deciding about when they
# stand at a junction wondering whether the walk is worth it.
#
# `viewpoint` joined them when the vistas layer started publishing. It is the
# case the doc's own title sentence names first - *"the blue-blazed offshoots
# that lead from the AT to a water source, a shelter, a privy, a viewpoint or
# a parking area"* - and ATC codes the spur type as "Spur (eg View, Camp)",
# so a view is half of what their own domain says a spur leads to. "Is the
# walk worth it" is exactly the question a named overlook answers.
DESTINATION_POI_TYPES = ("shelter", "water", "campsite", "resupply", "viewpoint")

# And which may not - the same decision, written down instead of left as an
# absence (#492).
#
# The two together must cover lib/poi_schema.POI_TYPES exactly, which
# tests/test_export_spurs.py asserts. That is the whole point of declaring
# this at all: a subset by OMISSION means adding a sixth POI category leaves
# it silently ineligible here, with no error, no warning and no failing test
# - the spurs leading to it publish `destination_poi_id: null` and the line
# detail sheet says nothing about where that trail goes.
#
# It is the shape of #469 through a different hole. There, export wrote
# `shelter.geojson` and this module read `poi_shelter.geojson`; 784 spurs
# published with a null destination and the run went green, because a missing
# POI file is a legal empty result. `poi_output_name()` closed that by giving
# the two ends one home. A category nobody remembered to classify reaches the
# same silence without anyone spelling anything differently.
#
# Being a partition rather than a filter is what makes the next category a
# decision somebody has to make, in a test that names the type it is waiting
# on, rather than a default nobody notices taking effect.
#
# `crossing` is here because it is a place the trail crosses water, not a
# place a spur goes to - it sits ON the centerline, so a blue-blazed side
# trail leading to one is not the thing a hiker is weighing at a junction.
# (It is also empty today, but that is a fact about the current export and
# would be the wrong reason: this list is about what a destination MEANS.)
#
# `privy` and `parking` are here for the two reasons the doc gives above,
# and they survived the layers actually shipping rather than being carried
# over unexamined. A privy is real, walked to, and now drawn on the map -
# what it is not is the answer to "where does this trail go". 272 of ATC's
# 316 privies are named for the shelter or campsite they stand behind ("Hurd
# Brook Lean-to Privy", "Mt. Algo Shelter Privy"; counted 2026-08-09), and
# that neighbour is the destination a hiker recognises - naming the privy
# would replace it with its outbuilding. Parking is
# an approach: ATC files those side trails as `Type=0` Access, which this
# export already filters out before a destination is looked for at all, so
# admitting parking here would mostly name a car park at the end of a spur
# that leads somewhere else.
NOT_A_DESTINATION_POI_TYPES = ("crossing", "privy", "parking")


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

    # Loud, like fetch_all.py and the other exporters' fail_if_incomplete()
    # gates - not the quiet `return {}` this used to be (#172), which exited
    # 0 on missing inputs while every sibling script fails. A run that cannot
    # read its inputs has nothing true to say, and saying nothing with a
    # green exit code is how an empty spurs.json ships.
    missing = []
    if not side_trails:
        missing.append("side_trails.geojson absent or empty - run fetch_all.py first")
    if not centerline_features:
        missing.append("centerline.geojson absent or empty - run fetch_all.py first")
    fail_if_incomplete(missing, label="Missing spur-export inputs")
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
