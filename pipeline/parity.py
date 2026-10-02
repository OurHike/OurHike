"""Shadow-run parity: a family's file from today's exporter against the dbt writer's, record by record.

    python parity.py podcasts --new data/processed/podcasts_episodes.json
    python parity.py stewards --new data/processed/stewards.json
    python parity.py nearby_trails --new data/processed/dbt/nearby_trails.geojson
    python parity.py network_overview --new data/processed/dbt/network_overview.geojson

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

Three optional parts, for a family whose records do not fit that (the trail
lines network's two GeoJSON files are the first):
- `key_of` reads a record's key where it is not a top-level field, as a
  GeoJSON feature's `properties.id` is not; `key` then only names it;
- `normalize` puts a record in the form it is compared in, where a part of
  it has no published order (a MultiLineString's parts);
- `explained` names the differences a decision or a classified improvement
  accounts for, each with its reason: printed, and not counted. Every other
  difference still exits 1, and the family's parity test holds each reason
  to a case where the two writers answer differently.

Exit 1 on any difference, so a CI step fails on one.
"""

from __future__ import annotations

import argparse
import functools
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
    key_of: Callable[[dict], str] | None = None
    normalize: Callable[[dict], dict] | None = None
    explained: Callable[[dict, dict], dict[str, str]] | None = None


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


def _network_old(name: str) -> dict:
    """One file export_nearby_trails.main() writes, from a whole run into a temporary folder.

    main() has no builder that stops short of writing, so it runs as a publish
    runs it, and the tiles, the shared-ground pairs and the manifest it writes
    beside the file are thrown away. Its own lines go to a buffer, so this
    step prints the comparison and nothing else.
    """
    import contextlib
    import io
    import tempfile

    import export_nearby_trails

    with tempfile.TemporaryDirectory() as out, contextlib.redirect_stdout(io.StringIO()):
        export_nearby_trails.OUT_DIR = Path(out)
        export_nearby_trails.main()
        return json.loads((Path(out) / name).read_text(encoding="utf-8"))


#: Why a network line's published id can differ between the two writers
#: (TL05), by case. tests/test_dbt_trail_lines_network_parity.py holds each to
#: a unit-test row where the two answer that way, so none outlives its reason.
NETWORK_ID_REASONS = {
    "globalid_in_any_case": (
        "an improvement (TL05): the SQL reads a layer's GlobalID whatever its case, then its OBJECTID, then "
        "Socrata's row id, where resolve_feature_id() matches only 'GlobalID' and falls back to the feature's "
        "server row id or to its place in the file"
    ),
    "feature_id_not_landed": (
        "expected by TL05's ledger row until the extract lands it: the extract lands a feature's properties and "
        "geometry and not its GeoJSON id, so a layer whose only id is that one is numbered by its place in the file"
    ),
}


def _network_id_reasons(old: dict, new: dict) -> dict[str, str]:
    """The `properties.id` differences that are only a line's id, each with its reason.

    A line is the same line in both files when its source, its other
    properties and its geometry are. Where such a line carries other ids in
    the two files, every id it carries is explained, by the case its ids
    show. Two positional ids for one line are never explained: both writers
    number a layer with no id in its file's order (int_trail_lines__network_judged),
    so a line they number differently is a defect.
    """

    def line(feature: dict) -> str:
        properties = {name: value for name, value in feature["properties"].items() if name != "id"}
        return canonical({"properties": properties, "geometry": feature["geometry"]})

    def ids(document: dict) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for feature in document.get("features") or []:
            found.setdefault(line(feature), []).append(str(feature["properties"]["id"]))
        return found

    def positional(feature_id: str) -> bool:
        return ":generated-" in feature_id

    old_ids, new_ids = ids(old), ids(new)
    reasons: dict[str, str] = {}
    for shared in old_ids.keys() & new_ids.keys():
        was, now = sorted(old_ids[shared]), sorted(new_ids[shared])
        if was == now:
            continue
        if all(positional(feature_id) for feature_id in was + now):
            continue
        case = "feature_id_not_landed" if all(positional(feature_id) for feature_id in now) else "globalid_in_any_case"
        for feature_id in set(was) | set(now):
            reasons[f"properties.id {feature_id}"] = NETWORK_ID_REASONS[case]
    return reasons


def _overview_key(feature: dict) -> str:
    """A sketch feature's group, write_overview()'s key: source, through route, blaze_color and trail_status."""
    properties = feature["properties"]
    return canonical([properties.get(name) for name in ("source", "name", "blaze_color", "trail_status")])


def _overview_parts_as_a_set(feature: dict) -> dict:
    """A sketch feature with its MultiLineString's parts sorted.

    Each writer lists a group's parts in its own record order, and the
    warehouse does not hold the fetched files' (pub_network_overview's
    header); a MultiLineString's parts draw the same in any order.
    """
    geometry = feature.get("geometry") or {}
    return {**feature, "geometry": {**geometry, "coordinates": sorted(geometry.get("coordinates") or [])}}


FAMILIES: dict[str, Family] = {
    "podcasts": Family(old=_podcasts_old, records="episodes", key="spotify_id", ordered=True),
    "stewards": Family(old=_stewards_old, records="stewards", key="provider", ordered=True),
    # `organizations`, beside the records, is compared whole as a top-level field.
    "registry": Family(old=_registry_old, records="sources", key="key", ordered=True),
    # The trail lines network: export_nearby_trails.py's two files, from one
    # run on the same input. A line is keyed by its published id, and an
    # id-only difference is explained by NETWORK_ID_REASONS, never dropped.
    "nearby_trails": Family(
        old=lambda: _network_old("nearby_trails.geojson"),
        records="features",
        key="properties.id",
        key_of=lambda feature: str(feature["properties"]["id"]),
        explained=_network_id_reasons,
    ),
    "network_overview": Family(
        old=lambda: _network_old("network_overview.geojson"),
        records="features",
        key="properties (source, name, blaze_color, trail_status)",
        ordered=True,
        key_of=_overview_key,
        normalize=_overview_parts_as_a_set,
    ),
}


# --- the points_of_interest family (#1793, stage 3) -------------------------
#
# Ten files, three exporters. The records are GeoJSON features, keyed by
# properties.id (`key_of`), and nearby_poi's one kind of deliberate difference
# is named by `explained`.


def _poi_id(feature: dict) -> str:
    return str(feature["properties"]["id"])


#: Why a POI can be in today's file and not in the dbt writer's, by case.
#: tests/test_dbt_points_of_interest_parity.py holds each to the fixture row
#: where the two writers answer that way, so none outlives its reason.
POI_REASONS = {
    "exact_copy": (
        "expected by decision 40, and accepted as an improvement on 2026-10-02: staging removes a row that is an "
        "exact copy of another in every column but the server's own row id (ELT.md, 'A dedupe may only remove "
        "exact copies, and the build proves it'), keeping the lowest OBJECTID, where export_nearby_poi.py "
        "publishes every copy as a pin of its own at the same spot"
    ),
}


def _row_id_order(value) -> tuple:
    """A source_feature_id's sort key: numbers numerically, then strings."""
    return (0, value, "") if isinstance(value, int | float) and not isinstance(value, bool) else (1, 0, str(value))


def _exact_copy_reasons(old: dict, new: dict) -> dict[str, str]:
    """The POIs today's file publishes and the dbt writer's does not, each an exact copy of one it does.

    A copy is a feature of the same layer that agrees with another on its
    geometry and on every property but `id` and `source_feature_id`, the
    server's own row id, and the one kept is the copy with the lowest id, as
    the staging dedupe keeps the lowest OBJECTID. A missing feature is
    explained only when the copy that is kept is in the new file; anything
    else the new file lacks, or has extra, is still a difference.
    """

    def body(feature: dict) -> tuple[str, str]:
        properties = {name: value for name, value in feature["properties"].items() if name not in ("id", "source_feature_id")}
        return feature["properties"]["source"], canonical({"geometry": feature["geometry"], "properties": properties})

    new_ids = {_poi_id(feature) for feature in new.get("features") or []}
    copies: dict[tuple[str, str], list[dict]] = {}
    for feature in old.get("features") or []:
        copies.setdefault(body(feature), []).append(feature)
    reasons: dict[str, str] = {}
    for group in copies.values():
        if len(group) < 2:
            continue
        kept, *dropped = sorted(group, key=lambda feature: _row_id_order(feature["properties"]["source_feature_id"]))
        if _poi_id(kept) not in new_ids:
            continue
        for feature in dropped:
            if _poi_id(feature) not in new_ids:
                reasons[f"properties.id {_poi_id(feature)}"] = POI_REASONS["exact_copy"]
    return reasons


@functools.cache
def _published_network() -> Path:
    """nearby_trails.geojson as export_nearby_trails.main() writes it, in a folder kept for this process.

    Both POI exporters read the published network: export_poi.py widens its
    corridor by the 500 ft ring around it (NETWORK_LINES_PATH), and
    export_nearby_poi.py clips its amenities to that ring and marks the
    trailheads whose every line is closed. A publish run writes the file
    first, so the old documents are built with it there, as the dbt models
    are built with int_trail_lines__network_published.
    """
    import contextlib
    import io
    import tempfile

    import export_nearby_trails

    out = Path(tempfile.mkdtemp(prefix="parity-network-"))
    with contextlib.redirect_stdout(io.StringIO()):
        export_nearby_trails.OUT_DIR = out
        export_nearby_trails.main()
    return out / "nearby_trails.geojson"


def _poi_by_type_old(poi_type: str) -> Callable[[], dict]:
    """export_poi.py's poi_<type>.geojson, as its own main() writes it.

    export_poi.py has no builder that returns the documents: main() writes
    all eight through GDAL, whose printing of a double is part of the shape
    being compared, so the old document is the file main() just wrote, read
    back. Every input is a raw file, a reviewed file in git or the published
    network (_published_network()), and nothing in main() fetches.
    """

    def old() -> dict:
        import export_poi

        export_poi.NETWORK_LINES_PATH = _published_network()
        export_poi.main()
        return json.loads((export_poi.OUT_DIR / f"{poi_type}.geojson").read_text(encoding="utf-8"))

    return old


def _nearby_poi_old() -> dict:
    """export_nearby_poi.py's nearby_poi.geojson, by its own functions in main()'s order, less the guide.

    main() itself cannot run on the fixtures: nynjtc_long_path_guide carries
    reaches_hikers true, so main() raises without the guide's page cache, and
    the guide is not ported (ELT.md ledger row PO36). Everything else is
    main()'s: each registered layer's build_records() in poi_sources()'s
    order, the network ring and the closed-trailhead mark against the
    published network (_published_network()), the place sites.
    """
    import export_nearby_poi as nearby

    registry = nearby.load_registry(nearby.ROOT / "sources.json")
    sources = nearby.poi_sources(registry)
    records: list[dict] = []
    for source in sources:
        features = json.loads((nearby.RAW_DIR / f"{source['key']}.geojson").read_text(encoding="utf-8")).get("features", [])
        records.extend(nearby.build_records(source, features)[0])
    network = _published_network()
    records, _ = nearby.clip_to_network(records, network, nearby.boundary_paths_for(sources))
    nearby.mark_closed_trailheads(records, network)
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
                old=_poi_by_type_old(poi_type), records="features", key="properties.id", ordered=True, key_of=_poi_id
            )
            for poi_type in ("shelter", "campsite", "water", "resupply", "viewpoint", "parking", "privy", "trailhead")
        },
        # Unordered: the layers' rows are read in file order, and three of the
        # layers come from base models that keep no row number.
        "nearby_poi": Family(
            old=_nearby_poi_old, records="features", key="properties.id", key_of=_poi_id, explained=_exact_copy_reasons
        ),
        "retired_poi": Family(old=_retired_poi_old, records="features", key="properties.id", ordered=True, key_of=_poi_id),
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

    def record_key(record: dict) -> str:
        return family.key_of(record) if family.key_of else str(record[family.key])

    def shaped(record: dict) -> dict:
        return family.normalize(record) if family.normalize else record

    def index(document: dict) -> dict[str, str]:
        return {record_key(record): canonical(drop(shaped(record))) for record in document.get(family.records) or []}

    a, b = index(old), index(new)
    found += [(f"{family.key} {key}", a.get(key), b.get(key)) for key in sorted(a.keys() | b.keys()) if a.get(key) != b.get(key)]
    if family.ordered:
        old_order = [record_key(record) for record in old.get(family.records) or []]
        new_order = [record_key(record) for record in new.get(family.records) or []]
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
    found = differences(old, new, family)
    count = len(old.get(family.records) or [])
    reasons = family.explained(old, new) if family.explained else {}
    explained = [difference for difference in found if difference[0] in reasons]
    for reason in dict.fromkeys(reasons[what] for what, _, _ in explained):
        named = [what for what, _, _ in explained if reasons[what] == reason]
        print(f"  explained, {len(named)}: {reason}")
        for what in named:
            print(f"    {what}")
    found = [difference for difference in found if difference[0] not in reasons]
    if not found:
        beyond = f" beyond the {len(explained)} explained above" if explained else ""
        print(f"{args.family}: no differences{beyond} across {count} {family.records}, keyed by {family.key}")
        return 0
    print(f"{args.family}: {len(found)} difference(s):")
    for what, a, b in found:
        print(f"  {what}\n    old: {a}\n    new: {b}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
