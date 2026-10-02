"""Shadow-run parity: a family's file from today's exporter against the dbt writer's, record by record.

    python parity.py podcasts --new data/processed/podcasts_episodes.json
    python parity.py stewards --new data/processed/stewards.json
    python parity.py elevation --new data/processed/dbt/elevation_profile.json --raw-dir data/raw
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

Four optional parts, for a family whose records do not fit that (the trail
lines network's two GeoJSON files are the first):
- `key_of` reads a record's key where it is not a top-level field, as a
  GeoJSON feature's `properties.id` is not; `key` then only names it;
- `normalize` puts a record in the form it is compared in, where a part of
  it has no published order (a MultiLineString's parts);
- `explained` names the differences a decision or a classified improvement
  accounts for, each with its reason: printed, and not counted. Every other
  difference still exits 1, and the family's parity test holds each reason
  to a case where the two writers answer differently;
- `new_shape` turns the writer's whole file into the shape the family's
  `old` returns, where the records are not a list of flat objects: the
  A.T.'s files (trails.geojson's features, trail_miles.json's and
  spurs.json's objects keyed by id).

Exit 1 on any difference, so a CI step fails on one.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
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
    # The file is a bare JSON array of records, as elevation_profile.json is,
    # rather than an object holding them: the new file is read as
    # {records: <the array>}, the shape `old` returns it in.
    bare_list: bool = False
    # The old document is built from make_dbt_fixtures.py's raw files rather
    # than from a file in git, so `old` takes the --raw-dir they are in.
    reads_raw_dir: bool = False
    # Top-level fields that hold the moment a run happened, such as the
    # conditions files' `generated_at`: two runs never agree on the value, so
    # each is held to its form (a UTC stamp, STAMP) on both sides instead.
    stamps: tuple[str, ...] = ()
    key_of: Callable[[dict], str] | None = None
    normalize: Callable[[dict], dict] | None = None
    explained: Callable[[dict, dict], dict[str, str]] | None = None
    # For a file whose records are not a list of flat objects (trails.geojson's
    # features key on a property; spurs.json keys on the object's own keys):
    # what turns the writer's file, read from `--new`, into that shape. The
    # family's `old` returns its document already in it.
    new_shape: Callable[[dict, Path], dict] | None = None


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


def _elevation_old(raw_dir: Path) -> dict:
    """export_elevation.build_profile over the raw files the warehouse was loaded from.

    The DEM is read through a copy of the tile index in a directory of its
    own, so the sampler's cache, which lives beside the index, starts cold:
    no elevation comes from what step_dem_sampling read on the dbt side, and
    two paths that read the DEM at different points cannot agree through it."""
    import shutil
    import tempfile

    import export_elevation

    with tempfile.TemporaryDirectory() as scratch:
        index = Path(scratch) / "tile_index.json"
        shutil.copy(raw_dir / "elevation" / "tile_index.json", index)
        records, _ = export_elevation.build_profile(
            raw_dir / "centerline.geojson",
            raw_dir / "half_mile_points_from_springer.geojson",
            index,
            export_elevation.SAMPLE_INTERVAL_METERS,
        )
    return {"samples": records}


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


# The trail_lines family's A.T. files (stage 3 of #1793 — Rebuild the data
# platform as dlt → dbt: seven contracted marts, a monthly refresh, published
# docs, and lighter phone downloads). export_trails.py and export_spurs.py run
# over the data/raw the warehouse was loaded from, with side_trails' coded
# domains read from the dbt var trail_lines_coded_domains, the frozen copy
# the dbt models decode with: the exporters fetch them live, and a CI runner
# has no ArcGIS to ask. tests/test_dbt_trail_lines_parity.py holds the var to
# the domains the exporters' own tests decode with.


def _trail_lines_coded_domain() -> Callable[[str | None, str], dict | None]:
    """lib/arcgis.get_field_coded_domain's answer, from the var: {code: label} for (the layer at url, field)."""
    import yaml

    root = Path(__file__).parent
    registry = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    key_by_url = {entry.get("url"): entry["key"] for entry in registry["sources"]}
    variables = yaml.safe_load((root / "dbt" / "dbt_project.yml").read_text(encoding="utf-8"))["vars"]
    domains: dict[tuple[str, str], dict[str, str]] = {}
    for source, field, code, label in variables["trail_lines_coded_domains"]:
        domains.setdefault((source, field), {})[code] = label
    return lambda url, field: domains.get((key_by_url.get(url), field))


@functools.cache
def _export_trails_run() -> Path:
    """export_trails.main() into a temporary directory, which it returns: one run feeds all three of its files.

    Its own lines go to a buffer, as _network_old's do, so the step prints the comparison and nothing else.
    """
    import contextlib
    import io
    import tempfile

    import export_trails

    out = Path(tempfile.mkdtemp(prefix="parity_trails_"))
    export_trails.get_field_coded_domain = _trail_lines_coded_domain()
    export_trails.OUT_DIR = out
    with contextlib.redirect_stdout(io.StringIO()):
        export_trails.main()
    return out


def _trails_records(document: dict, path: Path | None) -> dict:
    """trails.geojson's features as flat records keyed by their `id` property, each with its geometry and the
    feature's own members, so a feature-level `id` or a missing `type` would show."""
    return {
        **{name: value for name, value in document.items() if name != "features"},
        "features": [
            {
                **feature["properties"],
                "geometry": feature["geometry"],
                "feature_members": sorted(feature),
                "feature_type": feature["type"],
            }
            for feature in document["features"]
        ],
    }


def _trails_old() -> dict:
    """export_trails.py's trails.geojson with every coordinate cut to six decimals, as decision 8 cuts the dbt
    file's, by export_nearby_trails._rounded_geometry, the never-degenerate rule included. That is the one
    deliberate difference, applied to the old side, so every difference left is a defect."""
    from shapely.geometry import shape

    from export_nearby_trails import _rounded_geometry

    document = json.loads((_export_trails_run() / "trails.geojson").read_text(encoding="utf-8"))
    for feature in document["features"]:
        feature["geometry"] = _rounded_geometry(shape(feature["geometry"]))
    return _trails_records(document, None)


def _trail_miles_records(document: dict, path: Path) -> dict:
    """trail_miles.json as one record per chain, and `trails_sha256` as whether it names the trails.geojson beside
    it. The two paths' hashes differ by construction (decision 8 changes trails.geojson's bytes), so each file is
    asked what the phone asks of it (client/src/lib/trailData.ts): that it names the lines written with it."""
    trails = path.parent / "trails.geojson"
    names_its_trails = document.get("trails_sha256") == hashlib.sha256(trails.read_bytes()).hexdigest()
    return {
        **{name: value for name, value in document.items() if name not in ("miles", "trails_sha256")},
        "trails_sha256_names_its_trails_geojson": names_its_trails,
        "miles": [{"id": key, "miles": miles} for key, miles in document["miles"].items()],
    }


def _trail_miles_old() -> dict:
    path = _export_trails_run() / "trail_miles.json"
    return _trail_miles_records(json.loads(path.read_text(encoding="utf-8")), path)


def _trails_overview_records(document: dict, path: Path | None) -> dict:
    """trails_overview.geojson's one feature as one record per line of its MultiLineString."""
    (feature,) = document["features"]
    return {
        "type": document["type"],
        "feature": {name: value for name, value in feature.items() if name != "geometry"},
        "geometry_type": feature["geometry"]["type"],
        "lines": [{"line": index, "coordinates": line} for index, line in enumerate(feature["geometry"]["coordinates"])],
    }


def _trails_overview_old() -> dict:
    path = _export_trails_run() / "trails_overview.geojson"
    return _trails_overview_records(json.loads(path.read_text(encoding="utf-8")), path)


def _spurs_records(document: dict, path: Path | None) -> dict:
    """spurs.json, an object keyed by side-trail id, as one record per spur in key order."""
    return {"spurs": [{"id": key, **record} for key, record in document.items()]}


def _spurs_old() -> dict:
    """export_spurs.py's records over the same raw files, its Type domain the var's, and its destinations the POI
    files export_poi.py wrote, where there are any. CI's dbt job writes none, and int_trail_lines__spur_destinations
    has no rows until the points_of_interest mart publishes POIs, so today both sides name no destination."""
    import export_spurs

    raw = export_spurs.RAW_DIR
    domain = _trail_lines_coded_domain()(export_spurs.source_url(export_spurs.SIDE_TRAILS_KEY), export_spurs.TYPE_FIELD)
    records = export_spurs.build_spur_records(
        export_spurs.load_features(raw / "side_trails.geojson"),
        export_spurs.load_features(raw / "centerline.geojson"),
        export_spurs.load_destination_pois(),
        domain,
    )
    export_spurs.attach_junction_miles(records, raw / "centerline.geojson", raw / export_spurs.MARKERS_NAME)
    return _spurs_records(json.loads(json.dumps(records, sort_keys=True)), None)


def _club_sections_old() -> dict:
    """export_club_sections.build_output() over the same raw files. Its `source_edited` reads fetch_all.py's
    data/raw/manifest.json, which the CI fixture has none of, so there it is {} on both sides; on a live fetch the
    Python dates each layer and the dbt file cannot yet (pub_club_sections' header says why)."""
    import export_club_sections

    return json.loads(json.dumps(export_club_sections.build_output()))


FAMILIES: dict[str, Family] = {
    "podcasts": Family(old=_podcasts_old, records="episodes", key="spotify_id", ordered=True),
    "stewards": Family(old=_stewards_old, records="stewards", key="provider", ordered=True),
    # `organizations`, beside the records, is compared whole as a top-level field.
    "registry": Family(old=_registry_old, records="sources", key="key", ordered=True),
    # elevation_profile.json's records carry no id: each is keyed by its own
    # mile, which the profile publishes strictly increasing, so it is unique.
    "elevation": Family(
        old=_elevation_old, records="samples", key="distance_mi", ordered=True, bare_list=True, reads_raw_dir=True
    ),
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
    "trails": Family(old=_trails_old, records="features", key="id", ordered=True, new_shape=_trails_records),
    "trail_miles": Family(old=_trail_miles_old, records="miles", key="id", ordered=True, new_shape=_trail_miles_records),
    "trails_overview": Family(
        old=_trails_overview_old, records="lines", key="line", ordered=True, new_shape=_trails_overview_records
    ),
    "spurs": Family(old=_spurs_old, records="spurs", key="id", ordered=True, new_shape=_spurs_records),
    # `sources`, `source_edited` and `unattributed`, beside the clubs, are compared whole.
    "club_sections": Family(old=_club_sections_old, records="clubs", key="acronym", ordered=True),
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
    parser.add_argument(
        "--raw-dir", type=Path, default=Path("data/raw"), help="make_dbt_fixtures.py's files, for a family built from them"
    )
    args = parser.parse_args(argv)

    family = FAMILIES[args.family]
    old = family.old(args.raw_dir) if family.reads_raw_dir else family.old()
    new = json.loads(args.new.read_text(encoding="utf-8"))
    if family.new_shape is not None:
        new = family.new_shape(new, args.new)
    if family.bare_list:
        new = {family.records: new}
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
