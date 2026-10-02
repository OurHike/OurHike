"""Shadow-run parity: a family's file from today's exporter against the dbt writer's, record by record.

    python parity.py podcasts --new data/processed/podcasts_episodes.json
    python parity.py stewards --new data/processed/stewards.json

pipeline/ELT.md, "How a rule moves: shadow-run parity", is the design: both
paths read the same input, records are paired by their key, and each
record's canonical JSON (keys sorted, whitespace gone) is compared. The
answer is the list of (key, old, new) differences, never a count, so a
reviewer can see where they are and classify each one: expected by a
decision, an improvement, or a defect in the new path.

Whitespace, key order and the trailing newline are not differences. A
record's place in the list is, for a family whose order is published (the
podcast list is shown in the file's order), and so is every top-level field
beside the records.

A FAMILY JOINS by a row in FAMILIES: how to get the old document, where its
records are, and what keys them. The old document comes from the exporter's
own builder, not a file it wrote, when the exporter has one that needs no
network, as export_podcasts.build_document does.

Exit 1 on any difference, so a CI step fails on one.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Family:
    old: Callable[[], dict]
    records: str
    key: str
    ordered: bool = False
    volatile: tuple[str, ...] = ()
    # Applied to both documents before they are compared, for a family whose
    # records keep their key below the top level (a GeoJSON feature's id is in
    # its properties).
    normalize: Callable[[dict], dict] | None = None


def _podcasts_old() -> dict:
    import export_podcasts

    reference = json.loads(export_podcasts.REFERENCE_PATH.read_text(encoding="utf-8"))
    document, dropped = export_podcasts.build_document(reference)
    if dropped:
        raise SystemExit(f"export_podcasts.py drops {len(dropped)} row(s), so it would publish nothing: {dropped}")
    return document


def _stewards_old() -> dict:
    import export_sources

    return export_sources.build_output()


def _registry_old() -> dict:
    import export_sources

    return export_sources.build_registry()


FAMILIES: dict[str, Family] = {
    "podcasts": Family(old=_podcasts_old, records="episodes", key="spotify_id", ordered=True),
    "stewards": Family(old=_stewards_old, records="stewards", key="provider", ordered=True),
    # `organizations`, beside the records, is compared whole as a top-level field.
    "registry": Family(old=_registry_old, records="sources", key="key", ordered=True),
}


# --- the points_of_interest family (#1793, stage 3) -------------------------
#
# Ten files, three exporters. The records are GeoJSON features, keyed by
# properties.id, which _keyed_by_id() lifts beside each feature.


def _keyed_by_id(document: dict) -> dict:
    """The document with each feature's properties.id copied to `_id`, the key parity pairs features by."""
    return {
        **document,
        "features": [{**feature, "_id": feature["properties"]["id"]} for feature in document.get("features") or []],
    }


def _row_id_order(value) -> tuple:
    """A source_feature_id's sort key: numbers numerically, then strings."""
    return (0, value, "") if isinstance(value, int | float) and not isinstance(value, bool) else (1, 0, str(value))


def _without_exact_copies(document: dict) -> dict:
    """The document keyed by id, with each layer's exact copies collapsed to the copy with the lowest id.

    Decision 40's dedupe: a staging model removes a row only when it is an
    exact copy of another, differing in nothing but the server's own row id
    (pipeline/ELT.md, "A dedupe may only remove exact copies, and the build
    proves it"), and keeps the lowest OBJECTID. export_nearby_poi.py
    publishes every copy, under its own id (one in dec_primitive_campsites,
    four in dec_backcountry_features and two in nyc_public_restrooms on the
    live layers, ELT.md's key table). So both documents are compared with
    each layer's features that agree on everything but `id` and
    `source_feature_id` taken once, which hides how many copies a side
    publishes and nothing else. tests/test_dbt_points_of_interest_parity.py
    holds that the fixtures carry such a copy, so this is exercised.
    """
    seen: set[tuple[str, str]] = set()
    kept: list[dict] = []
    collapsed: list[str] = []
    features = sorted(
        document.get("features") or [],
        key=lambda feature: (feature["properties"]["source"], _row_id_order(feature["properties"]["source_feature_id"])),
    )
    for feature in features:
        body = {name: value for name, value in feature["properties"].items() if name not in ("id", "source_feature_id")}
        signature = (feature["properties"]["source"], canonical({"geometry": feature["geometry"], "properties": body}))
        if signature in seen:
            collapsed.append(feature["properties"]["id"])
            continue
        seen.add(signature)
        kept.append(feature)
    if collapsed:
        print(
            f"  {len(collapsed)} exact cop{'y' if len(collapsed) == 1 else 'ies'} collapsed (decision 40): {', '.join(collapsed)}"
        )
    return _keyed_by_id({**document, "features": kept})


def _poi_by_type_old(poi_type: str) -> Callable[[], dict]:
    """export_poi.py's poi_<type>.geojson, as its own main() writes it.

    export_poi.py has no builder that returns the documents: main() writes
    all eight through GDAL, whose printing of a double is part of the shape
    being compared, so the old document is the file main() just wrote, read
    back. Every input is a raw file or a reviewed file in git, and nothing
    in main() fetches.
    """

    def old() -> dict:
        import export_poi

        export_poi.main()
        return json.loads((export_poi.OUT_DIR / f"{poi_type}.geojson").read_text(encoding="utf-8"))

    return old


def _nearby_poi_old() -> dict:
    """export_nearby_poi.py's nearby_poi.geojson, by its own functions in main()'s order, less the guide.

    main() itself cannot run on the fixtures: nynjtc_long_path_guide carries
    reaches_hikers true, so main() raises without the guide's page cache, and
    the guide is not ported (ELT.md ledger row PO36). Everything else is
    main()'s: each registered layer's build_records() in poi_sources()'s
    order, the network ring, the closed-trailhead mark, the place sites.
    """
    import export_nearby_poi as nearby

    registry = nearby.load_registry(nearby.ROOT / "sources.json")
    sources = nearby.poi_sources(registry)
    records: list[dict] = []
    for source in sources:
        features = json.loads((nearby.RAW_DIR / f"{source['key']}.geojson").read_text(encoding="utf-8")).get("features", [])
        records.extend(nearby.build_records(source, features)[0])
    records, _ = nearby.clip_to_network(
        records, nearby.OUT_DIR / nearby.NETWORK_ARTIFACT_NAME, nearby.boundary_paths_for(sources)
    )
    nearby.mark_closed_trailheads(records, nearby.OUT_DIR / nearby.NETWORK_ARTIFACT_NAME)
    site_props = nearby.site_properties(nearby.group_place_sites(records))
    for record in records:
        record.update(site_props.get(record["id"], {}))
    return nearby.records_to_geojson(records)


def _retired_poi_old() -> dict:
    import export_retired_poi

    pois = json.loads(export_retired_poi.LEDGER_PATH.read_text(encoding="utf-8"))["pois"]
    collection, dangling = export_retired_poi.build(pois)
    if dangling:
        raise SystemExit(
            f"export_retired_poi.py refuses {len(dangling)} dangling successor(s), so it would publish nothing: {dangling}"
        )
    return collection


FAMILIES.update(
    {
        **{
            f"poi_{poi_type}": Family(
                old=_poi_by_type_old(poi_type), records="features", key="_id", ordered=True, normalize=_keyed_by_id
            )
            for poi_type in ("shelter", "campsite", "water", "resupply", "viewpoint", "parking", "privy", "trailhead")
        },
        # Unordered: the layers' rows are read in file order, and three of the
        # layers come from base models that keep no row number.
        "nearby_poi": Family(old=_nearby_poi_old, records="features", key="_id", normalize=_without_exact_copies),
        "retired_poi": Family(old=_retired_poi_old, records="features", key="_id", ordered=True, normalize=_keyed_by_id),
    }
)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def differences(old: dict, new: dict, family: Family) -> list[tuple[str, str | None, str | None]]:
    """(what, old, new) for every record and top-level field that differs, by key; empty when the two agree."""

    def drop(record: dict) -> dict:
        return {name: value for name, value in record.items() if name not in family.volatile}

    found: list[tuple[str, str | None, str | None]] = []
    for name in sorted((old.keys() | new.keys()) - {family.records}):
        a = canonical(old[name]) if name in old else None
        b = canonical(new[name]) if name in new else None
        if a != b:
            found.append((f"field {name}", a, b))

    def index(document: dict) -> dict[str, str]:
        return {str(record[family.key]): canonical(drop(record)) for record in document.get(family.records) or []}

    a, b = index(old), index(new)
    found += [(f"{family.key} {key}", a.get(key), b.get(key)) for key in sorted(a.keys() | b.keys()) if a.get(key) != b.get(key)]
    if family.ordered:
        old_order = [str(record[family.key]) for record in old.get(family.records) or []]
        new_order = [str(record[family.key]) for record in new.get(family.records) or []]
        if old_order != new_order:
            found.append(("order", canonical(old_order), canonical(new_order)))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("family", choices=sorted(FAMILIES))
    parser.add_argument("--new", type=Path, required=True, help="the file the family's pub_ writer wrote")
    args = parser.parse_args(argv)

    family = FAMILIES[args.family]
    old, new = family.old(), json.loads(args.new.read_text(encoding="utf-8"))
    if family.normalize is not None:
        old, new = family.normalize(old), family.normalize(new)
    found = differences(old, new, family)
    count = len(old.get(family.records) or [])
    if not found:
        print(f"{args.family}: no differences across {count} {family.records}, keyed by {family.key}")
        return 0
    print(f"{args.family}: {len(found)} difference(s):")
    for what, a, b in found:
        print(f"  {what}\n    old: {a}\n    new: {b}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
