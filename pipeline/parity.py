"""Shadow-run parity: a family's file from today's exporter against the dbt writer's, record by record.

    python parity.py podcasts --new data/processed/podcasts_episodes.json
    python parity.py stewards --new data/processed/stewards.json
    python parity.py nearby_trails --new data/processed/dbt/nearby_trails.geojson
    python parity.py network_overview --new data/processed/dbt/network_overview.geojson
    python parity.py places --new data/processed/dbt/places.json

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
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Family:
    old: Callable[[], dict]
    records: str
    key: str
    ordered: bool = False
    volatile: tuple[str, ...] = ()
    # Top-level fields that hold the moment a run happened, such as the
    # conditions files' `generated_at`: two runs never agree on the value, so
    # each is held to its form (a UTC stamp, STAMP) on both sides instead.
    stamps: tuple[str, ...] = ()
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


# The hourly conditions files. Their inputs, other than reference/atc_updates.json,
# are not in git: fixture mode builds the warehouse from make_dbt_fixtures.py's
# answers under data/raw/conditions/, so the old side reads those same answers
# through today's own parse and read.
RAW_DIR = Path(__file__).resolve().parent / "data" / "raw"
# _stamp_utc()'s two forms: isoformat() prints microseconds only when there are any.
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?Z")


def _atc_updates_old() -> dict:
    """export_atc_updates.py's document for reference/atc_updates.json, with whatever automatic rows its scrape cache gives."""
    import export_atc_updates
    from lib.atc_updates import file_problems, is_reviewed

    document = json.loads(export_atc_updates.REVIEWED_PATH.read_text(encoding="utf-8"))
    if not is_reviewed(document):
        raise SystemExit("reference/atc_updates.json is not reviewed, so export_atc_updates.py publishes nothing")
    if problems := file_problems(document):
        raise SystemExit(f"export_atc_updates.py refuses reference/atc_updates.json, so it publishes nothing: {problems}")
    automatic, _ = export_atc_updates.automatic_rows(document, export_atc_updates.cached_updates())
    return export_atc_updates.build_document(document, datetime.now(timezone.utc), automatic)


def _nynjtc_alerts_old() -> dict:
    """export_nynjtc_alerts.py's document for the WordPress answers fixture mode served, read as fetch_nynjtc_alerts.py reads them."""
    import export_nynjtc_alerts
    import fetch_nynjtc_alerts
    from lib.nynjtc_alerts import PLACE_TAXONOMIES, TRAIL_ALERTS_CATEGORY_ID, parse_alert, parse_terms

    answers = json.loads((RAW_DIR / "conditions" / "nynjtc_trail_alerts.json").read_text(encoding="utf-8"))
    vocabularies = {taxonomy: parse_terms(answers["terms"][taxonomy]) for taxonomy in PLACE_TAXONOMIES}
    posts = [post for post in answers["posts"] if TRAIL_ALERTS_CATEGORY_ID in (post.get("categories") or [])]
    parsed = [parse_alert(post, vocabularies) for post in posts]
    if not posts or None in parsed:
        raise SystemExit("fetch_nynjtc_alerts.py would leave its cache alone for these posts, so nothing new publishes")
    now = datetime.now(timezone.utc)
    alerts = {alert.slug: fetch_nynjtc_alerts.as_cache_entry(alert, now) for alert in parsed}
    return export_nynjtc_alerts.build_document(alerts, now)


class _ConditionsDatabase:
    """OurHike's Postgres as export_conditions.py reads it: extract/_fixtures.py's FixtureConnection, which fixture
    mode's extract read the warehouse's rows from, answering the same query text, with each row a tuple as
    psycopg's default cursor returns it."""

    def __init__(self):
        from extract._fixtures import POSTGRES_FIXTURE, FixtureConnection

        answers = json.loads((RAW_DIR / "conditions" / POSTGRES_FIXTURE).read_text(encoding="utf-8"))
        self.connection = FixtureConnection(answers)
        self.description: list = []
        self.rows: list = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql: str):
        self.description, rows = self.connection.answer(sql)
        self.rows = [tuple(row[column.name] for column in self.description) for row in rows]

    def fetchall(self) -> list:
        return list(self.rows)


def _conditions_old(key: str) -> dict:
    """export_conditions.py's document for one of its artifacts, through its own read_<key>() and build_document()."""
    import export_conditions

    rows = getattr(export_conditions, f"read_{key}")(_ConditionsDatabase())
    return export_conditions.build_document(key, rows, datetime.now(timezone.utc))


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


def _places_old() -> dict:
    """export_places.py's document for the input the dbt side reads, through its own build_output().

    The input is the fixture warehouse's: OPRHP's park layer as fixture mode
    landed it, and today's own nearby_trails.geojson, from export_nearby_trails.main()
    on the same raw layers (the file pub_nearby_trails matches, parity's
    nearby_trails family). Two of its inputs are files the dbt side does not
    read yet: the published waypoints and the A.T.'s trails.geojson come
    from int_places__waypoints and int_places__at_lines, interfaces with no
    rows until the points_of_interest and trail_lines marts are merged, so
    this side reads none of either. When they merge, this reads
    export_poi.py's, export_nearby_poi.py's and export_trails.py's files on
    the same raw layers.
    """
    import tempfile

    import export_places
    from lib.source_registry import load_registry

    with tempfile.TemporaryDirectory() as out:
        nearby_trails = Path(out) / "nearby_trails.geojson"
        nearby_trails.write_text(json.dumps(_network_old("nearby_trails.geojson")), encoding="utf-8")
        output, _ = export_places.build_output(
            load_registry(export_places.SOURCES_PATH),
            RAW_DIR / "external" / f"{export_places.PARKS_KEY}.geojson",
            Path(out) / "poi",
            Path(out) / "nearby_poi.geojson",
            RAW_DIR / export_places.COMMUNITIES_RAW,
            [nearby_trails, Path(out) / "trails.geojson"],
            datetime.now(timezone.utc),
        )
    return output


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
    # `reviewed_at`, beside the records, is compared whole as a top-level field.
    "atc_updates": Family(old=_atc_updates_old, records="atc_updates", key="atc_id", ordered=True, stamps=("generated_at",)),
    "nynjtc_alerts": Family(
        old=_nynjtc_alerts_old, records="nynjtc_alerts", key="notice_id", ordered=True, stamps=("generated_at",)
    ),
    "closures": Family(
        old=lambda: _conditions_old("closures"), records="closures", key="id", ordered=True, stamps=("generated_at",)
    ),
    "reports": Family(
        old=lambda: _conditions_old("reports"), records="reports", key="id", ordered=True, stamps=("generated_at",)
    ),
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
    # places.json, keyed by each place's `id`, in the file's order (kind, name,
    # id). `trailRadiusMiles` and `trailMilesMeasured`, beside the records, are
    # compared whole as top-level fields.
    "places": Family(old=_places_old, records="places", key="id", ordered=True, stamps=("generated_at",)),
}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def differences(old: dict, new: dict, family: Family) -> list[tuple[str, str | None, str | None]]:
    """(what, old, new) for every record and top-level field that differs, by key; empty when the two agree."""

    def drop(record: dict) -> dict:
        return {name: value for name, value in record.items() if name not in family.volatile}

    found: list[tuple[str, str | None, str | None]] = []
    for name in sorted((old.keys() | new.keys()) - {family.records, *family.stamps}):
        a = canonical(old[name]) if name in old else None
        b = canonical(new[name]) if name in new else None
        if a != b:
            found.append((f"field {name}", a, b))
    for name in family.stamps:
        if not all(isinstance(document.get(name), str) and STAMP.fullmatch(document[name]) for document in (old, new)):
            found.append((f"field {name}", canonical(old.get(name)), canonical(new.get(name))))

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
