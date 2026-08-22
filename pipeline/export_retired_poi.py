"""Publish the tombstones: every POI id that has ever been retired (#673).

features/POI_IDENTITY.md section 4 is the design. The property this serves
is the one that doc states once: *every id ever published resolves to
something - a live POI, or a tombstone that says what happened*. The live
half is `poi_*.geojson`; this is the other half, and without it a hiker
whose photos are anchored to a shelter ATC dropped last September gets a
card that renders nothing at all rather than one that says what happened
to the place.

WHY THIS IS NOT CALLED `poi_retired.geojson`

Because `poi_*.geojson` is not a wildcard in this repository, it is a
namespace with an invariant, and three separate consumers already enforce
it:

  - `verify_release.check_poi_identity` (check 21) reads every manifest key
    matching `poi_*.geojson` and FAILS any feature whose id is not a LIVE
    ledger row. A file of retired ids under that name would fail check 21
    once per tombstone, by construction;
  - `publish.referenced_photo_keys` walks the same glob to collect the
    photo promises a publish is about to make;
  - `lib/poi_schema.POI_TYPES` and the client's own `poiKey()` both build
    the name as `poi_{poi_type}.geojson`, so `poi_retired` reads as a ninth
    POI type to every person and every tool that has learned the pattern.

The design doc wrote the name before check 21 existed (it landed with
#672, the day before this). `retired_poi.geojson` sits outside the glob,
which is the whole point, and `spurs.json` is the precedent for an
artifact that is neither a POI type nor a trail. Getting this right BEFORE
the first publish is not fussiness: `lib/r2_keys.py` explains that a key in
this bucket is a URL deployed phones already request, so a name that lands
wrong cannot be renamed afterwards - only abandoned and served forever
beside its replacement.

A NOTE ON WHAT r2_keys ACTUALLY GATES

features/POI_IDENTITY.md says "`lib/r2_keys.py` will refuse the key until
it is declared". Measured against the code on 2026-08-19, that is not true
of a root-level artifact: `validate_key` accepts `retired_poi.geojson`,
`poi_retired.geojson` and `tombstones.geojson` alike, because it gates
top-level PREFIXES, extensions, banned words and version-ish spellings -
not a per-artifact allowlist. The real gates a new artifact must pass
through are `publish.collect_artifacts` (which must learn to emit it) and
`tests/test_published_key_contract.py` (which holds the keys the client
builds against the keys publish actually writes). Said here because the
doc's sentence would otherwise send the next person looking for a
declaration list that does not exist.

HOW LONG A TOMBSTONE PUBLISHES: forever. See `lib/poi_identity.retired_rows`
for the arithmetic behind that answer and what would change it.

WHAT IS PUBLISHED BUT NOT YET FETCHED

R2_LAYOUT.md's "Adding an artifact" checklist has five steps. Steps 1, 2 and
4 are done here (the name, `publish.collect_artifacts`, and
`tests/test_r2_keys.py`). Steps 3 and 5 - the client learning the key, and
treating its absence as "no tombstones" the way it already treats
`spurs.json` - are deliberately NOT done yet, and the reason is a hiker's
download rather than an oversight. `client/src/lib/config.ts` says of its
POI list: "This list is the download list, so it is also the size of a
hiker's first fetch." Adding a key the client fetches and nothing renders
spends a hiker's bytes on a file with no consumer. The tombstone CARD is
#673's part (d), and the key belongs in `config.ts` in the same change that
gives it something to draw.

Publishing ahead of that is still the right order: the artifact has to
exist in a release before a client build can be written against it, and
`verify_release` check 21 holds it honest from the day it lands.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.hashing import sha256_file
from lib.poi_identity import live_rows, resolve, retired_rows

ROOT = Path(__file__).parent
LEDGER_PATH = ROOT / "reference" / "poi_identity.json"
OUT_PATH = ROOT / "data" / "processed" / "retired_poi.geojson"
MANIFEST_PATH = ROOT / "data" / "processed" / "retired_poi_manifest.json"


def tombstone(poi_id: str, row: dict) -> dict:
    """One retired row as a GeoJSON feature.

    A FeatureCollection rather than a JSON table because the position is the
    point: a tombstone card wants to show where the place WAS, and a client
    that already parses `poi_*.geojson` needs no second reader for this.

    `superseded_by` is omitted rather than nulled when there is none, which
    is this repository's standing rule and load-bearing here: absent means
    "nothing took this place's place", and a null would invite a reader to
    treat the two as one state. Most tombstones have no successor.
    """
    properties = {
        "id": poi_id,
        "poi_type": row["poi_type"],
        # Required, not optional: the card's whole sentence is built from
        # it, and a tombstone that cannot say who dropped the place is one
        # the client has to describe vaguely or not at all. See
        # lib/poi_identity.TOMBSTONE_PROPERTIES for why this is published
        # rather than split off the id.
        "source": row["source"],
        "retired": row["retired"],
    }
    if row.get("name"):
        properties["name"] = row["name"]
    if row.get("superseded_by"):
        properties["superseded_by"] = row["superseded_by"]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
        "properties": properties,
    }


def build(pois: dict) -> tuple[dict, list[str]]:
    """The tombstone collection, and the dangling edges worth refusing over.

    A `superseded_by` that does not resolve to a live row is a broken
    promise rather than a cosmetic flaw: it is the pointer a hiker's photos
    follow, and one that leads nowhere strands them somewhere the card
    cannot explain. `reconcile_poi_identity.apply_supersession` refuses to
    write such an edge in the first place, so anything found here came from
    a ledger edited by hand - which is exactly the case a check exists for.
    """
    retired = retired_rows(pois)
    dangling = [
        f"{poi_id}: superseded_by {row['superseded_by']}, which resolves to no live row"
        for poi_id, row in sorted(retired.items())
        if row.get("superseded_by") and resolve(pois, poi_id) is None
    ]
    collection = {
        "type": "FeatureCollection",
        "features": [tombstone(poi_id, retired[poi_id]) for poi_id in sorted(retired)],
    }
    return collection, dangling


def main() -> dict:
    if not LEDGER_PATH.exists():
        # The pre-#671 world: no ledger, so nothing has ever been retired
        # and there is nothing to say. Not an error - the same posture
        # export_poi.apply_ledger_ids takes on a missing ledger.
        print(f"No identity ledger at {LEDGER_PATH} - nothing to publish.")
        return {}

    pois = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))["pois"]
    collection, dangling = build(pois)
    if dangling:
        raise SystemExit(
            "These ledger rows point at a successor that is not live:\n  - " + "\n  - ".join(dangling) + "\n"
            "A tombstone's superseded_by is what re-anchors a hiker's photos; an edge that leads "
            "nowhere strands them. Fix the ledger (or the `merged_into` override behind it) and re-run."
        )

    features = collection["features"]
    superseded = sum(1 for feature in features if feature["properties"].get("superseded_by"))
    print(f"{len(features)} tombstones ({superseded} superseded) against {len(live_rows(pois))} live rows.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(collection, separators=(",", ":"), sort_keys=True))

    manifest = {
        "path": str(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "retired_count": len(features),
        "superseded_count": superseded,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"Tombstones -> {OUT_PATH}\nManifest -> {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    main()
