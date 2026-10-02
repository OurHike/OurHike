"""Shadow-run parity: a family's file from today's exporter against the dbt writer's, record by record.

    python parity.py podcasts --new data/processed/podcasts_episodes.json
    python parity.py stewards --new data/processed/stewards.json
    python parity.py elevation --new data/processed/dbt/elevation_profile.json --raw-dir data/raw
    python parity.py trail_graph_elevation --new data/processed/dbt/trail_graph_elevation.json --raw-dir data/raw --warehouse data/warehouse.duckdb
    python parity.py nearby_trails --new data/processed/dbt/nearby_trails.geojson
    python parity.py network_overview --new data/processed/dbt/network_overview.geojson
    python parity.py suggested_hikes --new data/processed/dbt/suggested_hikes.json --raw-dir data/raw
    python parity.py suggested_hikes_detail --new data/processed/dbt/suggested_hikes_detail.json --raw-dir data/raw
    python parity.py highlights --new data/processed/dbt/highlights.json --raw-dir data/raw
    python parity.py places --new data/processed/dbt/places.json
    python parity.py challenges --new data/processed/dbt/challenges.json

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

`--json-dir DIR` also writes the comparison as `DIR/<family>.json`
(RESULT_FORMAT, written by result_document()), for gate_report.py, which
turns every family's result into decision 30's per-key report. The console
lines and the exit code are the same with or without it. The file holds what
the console prints, plus what a reader of many families needs: which file
was compared, each difference's changed field paths (changed_fields()), the
fields compared by form only (`stamps`) or dropped (`volatile`), and the
records' source keys on each side (record_sources()). An old side that
refuses (the SystemExit some builders raise) is written as `old_side_refused`
before the exit, so a refusal reads as one and not as a missing run.
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
    # The old side's input is rows the build itself made, the junction graph's
    # edges, which today's exporters read from files the fixtures have none
    # of, so `old` takes --raw-dir and --warehouse.
    reads_warehouse: bool = False
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


def _graph_edges(warehouse: Path) -> tuple[dict, list]:
    """trail_graph.json's `edges` and trail_graph_geometry.json's entries, as int_trail_network__edges holds them.

    Both network elevation exporters read only these: each edge's `source`,
    `from` and `to`, and its published vertices, in edge order."""
    import duckdb

    with duckdb.connect(str(warehouse), read_only=True) as con:
        rows = con.execute(
            "select source_key, from_node, to_node, geom_geojson from intermediate.int_trail_network__edges order by edge_index"
        ).fetchall()
    graph = {"edges": [{"source": source, "from": start, "to": end} for source, start, end, _ in rows]}
    return graph, [json.loads(geom)["coordinates"] for *_, geom in rows]


@functools.cache
def _graph_companions_old(raw_dir: Path, warehouse: Path) -> tuple[list, list]:
    """export_network_elevation.build and export_network_profile.build over the build's own graph.

    In publish-vector-data.yml's order on one cold copy of the tile index:
    export_elevation.py's A.T. profile first, then the climbs, then the
    profiles, so the sampler's cache answers an edge point keyed like an
    A.T. point with the A.T.'s pixel on this side exactly as
    step_dem_sampling's one question does on the dbt side."""
    import shutil
    import tempfile

    import export_elevation
    import export_network_elevation
    import export_network_profile

    graph, geometry = _graph_edges(warehouse)
    with tempfile.TemporaryDirectory() as scratch:
        index = Path(scratch) / "tile_index.json"
        shutil.copy(raw_dir / "elevation" / "tile_index.json", index)
        export_elevation.build_profile(
            raw_dir / "centerline.geojson",
            raw_dir / "half_mile_points_from_springer.geojson",
            index,
            export_elevation.SAMPLE_INTERVAL_METERS,
        )
        sampler = export_elevation.ElevationSampler.for_index(index)
        try:
            climbs, _stats = export_network_elevation.build(graph, geometry, sampler)
        finally:
            sampler.close()
        sampler = export_elevation.ElevationSampler.for_index(index)
        try:
            profiles, _stats, _seam = export_network_profile.build(graph, geometry, sampler)
        finally:
            sampler.close()
    return climbs, profiles


def _by_edge(entries: list) -> dict:
    """An index-aligned companion array as records keyed by their place, the only key its entries have."""
    return {"edges": [{"edge_index": index, "entry": entry} for index, entry in enumerate(entries)]}


# The hourly conditions files. Their inputs, other than reference/atc_updates.json,
# are not in git: fixture mode builds the warehouse from make_dbt_fixtures.py's
# answers under data/raw/conditions/, so the old side reads those same answers
# through today's own parse and read.
RAW_DIR = Path(__file__).resolve().parent / "data" / "raw"
# _stamp_utc()'s two forms: isoformat() prints microseconds only when there are any.
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?Z")


def _atc_scrape_cache(answers: dict, folder: Path) -> Path:
    """The cache fetch_atc_updates.py's own main() writes from ATC's pages as fixture mode served them.

    Only the transport is swapped: its session gets extract/_fixtures.py's
    adapter, serving the same file's listing pages and update pages by URL,
    and its CACHE_PATH points into `folder`. The listing walk, plan_fetches(),
    the parse, the zero-failure rule and `listed` all run as an hourly run
    runs them.
    """
    import contextlib
    import io

    import fetch_atc_updates
    from extract._fixtures import FixtureAdapter, text_answers

    adapter = FixtureAdapter({}, {}, {}, pages=text_answers(answers))
    real_session, real_cache = fetch_atc_updates.atc_session, fetch_atc_updates.CACHE_PATH

    def served_session(session=None):
        named = real_session(session)
        named.mount("https://", adapter)
        return named

    fetch_atc_updates.atc_session, fetch_atc_updates.CACHE_PATH = served_session, folder / "atc_updates.json"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            failed = fetch_atc_updates.main()
    finally:
        fetch_atc_updates.atc_session, fetch_atc_updates.CACHE_PATH = real_session, real_cache
    if failed:
        raise SystemExit("fetch_atc_updates.py refuses the pages fixture mode served, so it would cache nothing new")
    return folder / "atc_updates.json"


def _atc_updates_old() -> dict:
    """export_atc_updates.py's document for reference/atc_updates.json, with the automatic rows its scrape gives.

    The scrape is fetch_atc_updates.py's own run over the pages fixture mode
    served (RAW_DIR's conditions/atc_trail_updates.json), where that file
    exists, so both sides read the same pages; otherwise whatever cache a real
    fetch left in data/raw/.
    """
    import tempfile

    import export_atc_updates
    from extract._fixtures import CONDITIONS_DIR, TEXT_FIXTURES
    from lib.atc_updates import file_problems, is_reviewed

    document = json.loads(export_atc_updates.REVIEWED_PATH.read_text(encoding="utf-8"))
    if not is_reviewed(document):
        raise SystemExit("reference/atc_updates.json is not reviewed, so export_atc_updates.py publishes nothing")
    if problems := file_problems(document):
        raise SystemExit(f"export_atc_updates.py refuses reference/atc_updates.json, so it publishes nothing: {problems}")
    served = RAW_DIR / CONDITIONS_DIR / TEXT_FIXTURES["atc_trail_updates"]
    with tempfile.TemporaryDirectory() as folder:
        cache = _atc_scrape_cache(json.loads(served.read_text(encoding="utf-8")), Path(folder)) if served.exists() else None
        automatic, _ = export_atc_updates.automatic_rows(document, export_atc_updates.cached_updates(cache))
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


def _weather_alerts_old(raw_dir: Path) -> dict:
    """export_weather_alerts.py's bake() over the NWS body fixture mode served and the weather squares, as its main() reads them.

    Both are under --raw-dir: conditions/nws_alerts.json, the body fixture
    mode served the extract, and weather/squares.json, the file
    step_weather_squares.py landed for the dbt side, refused as main() refuses
    one from before each square's zones were listed.
    """
    import export_weather_alerts

    squares = json.loads((raw_dir / "weather" / "squares.json").read_text(encoding="utf-8"))
    if "zones" not in squares:
        raise SystemExit(f"{raw_dir}/weather/squares.json predates each square's zones, so export_weather_alerts.py refuses it")
    body = json.loads((raw_dir / "conditions" / "nws_alerts.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    return export_weather_alerts.bake(squares, body, now, now)


def _work_projects_old() -> dict:
    """export_work_projects.py's file for reference/work_projects.json, from its own main(), written into a temporary folder.

    It has no builder that returns the document, so main() runs as a bake runs
    it, with only OUT_DIR, OUT_PATH and MANIFEST_PATH moved, and the file it
    wrote is read back.
    """
    import contextlib
    import io
    import tempfile

    import export_work_projects

    names = ("OUT_DIR", "OUT_PATH", "MANIFEST_PATH")
    real = {name: getattr(export_work_projects, name) for name in names}
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        moved = {"OUT_DIR": out, "OUT_PATH": out / "work_projects.json", "MANIFEST_PATH": out / "manifest.json"}
        for name, path in moved.items():
            setattr(export_work_projects, name, path)
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = export_work_projects.main()
        finally:
            for name, path in real.items():
                setattr(export_work_projects, name, path)
        if code != 0:
            raise SystemExit("export_work_projects.py refuses reference/work_projects.json, so it publishes nothing")
        if not moved["OUT_PATH"].exists():
            raise SystemExit("reference/work_projects.json is not reviewed, so export_work_projects.py publishes nothing")
        return json.loads(moved["OUT_PATH"].read_text(encoding="utf-8"))


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

    Every input is today's own file on the fixture warehouse's raw layers,
    each the one the dbt side's mart matches in its own parity line:
    - OPRHP's park layer and ATC's Communities, as fixture mode landed them;
    - nearby_trails.geojson, from export_nearby_trails.main()
      (_published_network(), which the POI exporters below read too);
    - trails.geojson, from export_trails.main() (_export_trails_run()), cut
      to six decimals as _trails_old() cuts it, because the dbt side measures
      the trail_lines mart's geometry, which is the cut file's (decision 8):
      measured 2026-10-02 on 1,546 real places, the cut moves one lot's
      trailMiles by a tenth, 17.8 to 17.9, and nothing else;
    - the trailhead, parking and resupply poi_<type>.geojson files, from
      export_poi.main(), as _poi_by_type_old() runs it;
    - nearby_poi.geojson, as _nearby_poi_old() builds it.

    Those helpers are the other families' parity code, called as they are;
    this only writes their documents where build_output() reads them.
    """
    import contextlib
    import io
    import tempfile

    from shapely.geometry import shape

    import export_places
    import export_poi
    from export_nearby_trails import _rounded_geometry
    from lib.source_registry import load_registry

    network = _published_network()
    export_poi.NETWORK_LINES_PATH = network
    with contextlib.redirect_stdout(io.StringIO()):
        export_poi.main()
    trails = json.loads((_export_trails_run() / "trails.geojson").read_text(encoding="utf-8"))
    for feature in trails["features"]:
        feature["geometry"] = _rounded_geometry(shape(feature["geometry"]))
    with tempfile.TemporaryDirectory() as out:
        trails_path = Path(out) / "trails.geojson"
        trails_path.write_text(json.dumps(trails), encoding="utf-8")
        nearby_poi = Path(out) / "nearby_poi.geojson"
        nearby_poi.write_text(json.dumps(_nearby_poi_old()), encoding="utf-8")
        output, _ = export_places.build_output(
            load_registry(export_places.SOURCES_PATH),
            RAW_DIR / "external" / f"{export_places.PARKS_KEY}.geojson",
            export_poi.OUT_DIR,
            nearby_poi,
            RAW_DIR / export_places.COMMUNITIES_RAW,
            [network, trails_path],
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


@functools.cache
def _published_pois() -> Path:
    """The poi_<type>.geojson files export_poi.main() writes, in a folder kept for this process: what
    export_spurs.py's load_destination_pois() reads in a publish run, from the same raw files and published network
    (_published_network()) the points_of_interest mart is built from.

    A folder of its own, never data/processed/poi: the poi_<type> parity lines and any earlier run write there, and
    a POI file one of them left made export_spurs.py name a destination the dbt side never saw (side_trails:
    spur-to-shelter, measured by the lead 2026-10-02). export_poi.py's module paths are put back afterwards, so the
    other families in the process see what they would have.
    """
    import contextlib
    import io
    import tempfile

    import export_poi

    out = Path(tempfile.mkdtemp(prefix="parity-poi-")) / "poi"
    saved = export_poi.OUT_DIR, export_poi.NETWORK_LINES_PATH
    try:
        export_poi.OUT_DIR = out
        export_poi.NETWORK_LINES_PATH = _published_network()
        with contextlib.redirect_stdout(io.StringIO()):
            export_poi.main()
    finally:
        export_poi.OUT_DIR, export_poi.NETWORK_LINES_PATH = saved
    return out


def _spurs_old() -> dict:
    """export_spurs.py's records over the same raw files, its Type domain the var's, and its destinations the POIs
    export_poi.py writes from them (_published_pois()), as int_trail_lines__spur_destinations reads the
    points_of_interest mart's."""
    import export_spurs

    raw = export_spurs.RAW_DIR
    domain = _trail_lines_coded_domain()(export_spurs.source_url(export_spurs.SIDE_TRAILS_KEY), export_spurs.TYPE_FIELD)
    records = export_spurs.build_spur_records(
        export_spurs.load_features(raw / "side_trails.geojson"),
        export_spurs.load_features(raw / "centerline.geojson"),
        export_spurs.load_destination_pois(_published_pois()),
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


# The suggested_hikes family: export_suggested_hikes.py's shelf and details,
# and export_highlights.py's file. The Hike Finder's pages are not in git, so
# fixture mode built the warehouse from make_dbt_fixtures.py's under
# <raw-dir>/hikefinder/, and the old side reads those same pages through
# fetch_hikefinder.py's own parse into its cache, routes them with
# route_hikefinder.py's own build_results(), and builds the records with
# export_suggested_hikes.py's build_document(), as a publish runs the three.
# Both sides route over one graph: the warehouse's (beside <raw-dir>, as CI
# lays it out), written out in route_hikefinder.py's three files by
# step_form_route.graph_files() and loaded by route_hikefinder.load_graph(),
# which is how trail_graph.json reaches route_hikefinder.py today.


def _hikefinder_cache(folder: Path, gpx_dir: Path) -> dict:
    """fetch_hikefinder.py's cache for the pages fixture mode served: parse_hike(), as_cache_entry(), and a GPX
    stored as store_gpx() stores one, only where it parses to a track point."""
    from urllib.parse import urljoin

    import export_suggested_hikes
    from lib.hikefinder import DETAIL_PATH, SOURCE_KEY, as_cache_entry, listing_ids, parse_gpx, parse_hike
    from lib.source_registry import find_source, load_registry

    base = find_source(load_registry(export_suggested_hikes.SOURCES_PATH), SOURCE_KEY)["url"].rstrip("/") + "/"
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    hikes: dict[str, dict] = {}
    for hike_id in listing_ids((folder / "hikes.html").read_text(encoding="utf-8")):
        page = (folder / f"hike-{hike_id}.html").read_text(encoding="utf-8")
        hike = parse_hike(page, hike_id, urljoin(base, DETAIL_PATH.format(id=hike_id)))
        if hike is None:
            continue
        entry = as_cache_entry(hike, stamp)
        entry["gpx_file"] = None
        track = folder / f"track-{hike_id}.gpx"
        if hike.has_published_route and track.exists() and parse_gpx(track.read_text(encoding="utf-8")) is not None:
            (gpx_dir / f"{hike_id}.gpx").write_text(track.read_text(encoding="utf-8"), encoding="utf-8")
            entry["gpx_file"] = f"{hike_id}.gpx"
        hikes[str(hike_id)] = entry
    return hikes


def _suggested_hikes_old(part: str, raw_dir: Path) -> dict | None:
    """export_suggested_hikes.py's shelf (`part` "shelf") or every detail ("details"), or None where its main()
    writes no file: a source that does not reach hikers, an export with no hike, or no hike that ships."""
    import tempfile

    import duckdb

    import export_suggested_hikes
    import route_hikefinder
    import step_form_route
    from lib.hikefinder import SOURCE_KEY
    from lib.source_registry import find_source, load_registry

    source = find_source(load_registry(export_suggested_hikes.SOURCES_PATH), SOURCE_KEY)
    if source is None or not source.get("reaches_hikers"):
        return None
    steward = source.get("steward") or source.get("attribution")
    with tempfile.TemporaryDirectory() as scratch:
        graph_dir, gpx_dir = Path(scratch) / "graph", Path(scratch) / "gpx"
        graph_dir.mkdir()
        gpx_dir.mkdir()
        cache = _hikefinder_cache(raw_dir / "hikefinder", gpx_dir)
        if not cache:
            return None
        with duckdb.connect(str(raw_dir.parent / "warehouse.duckdb"), read_only=True) as con:
            step_form_route.graph_files(con, graph_dir)
        starts = [(hike["start"]["lon"], hike["start"]["lat"]) for hike in cache.values() if hike.get("start")]
        graph = route_hikefinder.load_graph(graph_dir, starts)
        results = route_hikefinder.build_results(graph, cache, gpx_dir)
        routes = {str(result["hike"]["id"]): result["formed"].to_dict() for result in results}
        document, _ = export_suggested_hikes.build_document(graph, cache, routes, steward, datetime.now(timezone.utc))
    if not document["hikes"]:
        return None
    halves = [export_suggested_hikes.split_record(record) for record in document["hikes"]]
    if part == "shelf":
        return {**document, "hikes": [shelf for shelf, _ in halves]}
    return {"details": [detail for _, detail in halves]}


def _highlights_old(raw_dir: Path) -> dict:
    """export_highlights.py's file: the curated list in git resolved against the published POIs and club sections,
    each read by its own loader.

    export_poi.py and export_club_sections.py do not run in CI, so the POIs and clubs are the ones this run's dbt
    writers wrote beside <raw-dir> (data/processed/dbt/), which their own parity lines hold to those exporters: the
    eight poi_<type>.geojson files, copied under the names load_published_pois() reads (poi_output_name()), and
    club_sections.json. The rules are held row by row by the unit tests and tests/test_dbt_suggested_hikes_parity.py;
    this holds the real reference/highlights.json against the fixture POIs."""
    import shutil
    import tempfile

    import export_highlights
    from lib.poi_schema import POI_TYPES, poi_output_name

    written = raw_dir.parent / "processed" / "dbt"
    with tempfile.TemporaryDirectory() as scratch:
        for poi_type in POI_TYPES:
            if (written / f"poi_{poi_type}.geojson").exists():
                shutil.copyfile(written / f"poi_{poi_type}.geojson", Path(scratch) / poi_output_name(poi_type))
        pois = export_highlights.load_published_pois(Path(scratch))
    output, _, _ = export_highlights.build_output(
        export_highlights.load_curated(), pois, export_highlights.load_club_runs(written / "club_sections.json")
    )
    return output


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
    # The junction graph's two elevation companions: index-aligned arrays
    # whose entries carry no id, so each is keyed by its place, which is the
    # edge it describes.
    "trail_graph_elevation": Family(
        old=lambda raw_dir, warehouse: _by_edge(_graph_companions_old(raw_dir, warehouse)[0]),
        records="edges",
        key="edge_index",
        ordered=True,
        reads_warehouse=True,
        new_shape=lambda new, _path: _by_edge(new),
    ),
    "trail_graph_profile": Family(
        old=lambda raw_dir, warehouse: _by_edge(_graph_companions_old(raw_dir, warehouse)[1]),
        records="edges",
        key="edge_index",
        ordered=True,
        reads_warehouse=True,
        new_shape=lambda new, _path: _by_edge(new),
    ),
    # `reviewed_at`, beside the records, is compared whole as a top-level field.
    "atc_updates": Family(old=_atc_updates_old, records="atc_updates", key="atc_id", ordered=True, stamps=("generated_at",)),
    "nynjtc_alerts": Family(
        old=_nynjtc_alerts_old, records="nynjtc_alerts", key="notice_id", ordered=True, stamps=("generated_at",)
    ),
    # `release`, `zone_files`, `nws_updated` and `unknown_zones`, beside the
    # alerts, are compared whole; `fetched_at` is when each side asked NWS.
    "weather_alerts": Family(
        old=_weather_alerts_old,
        records="alerts",
        key="id",
        ordered=True,
        reads_raw_dir=True,
        stamps=("generated_at", "fetched_at"),
    ),
    # `reviewed_at`, beside the rows, is compared whole as a top-level field.
    "work_projects": Family(old=_work_projects_old, records="work_projects", key="id", ordered=True, stamps=("generated_at",)),
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
    # The suggested_hikes family. The shelf and the details are one run of
    # export_suggested_hikes.py, split as split_record() splits each record;
    # each is keyed by the hike's own id, in hike-number order. Either answers
    # None, a file not written, when no hike ships.
    "suggested_hikes": Family(
        old=lambda raw_dir: _suggested_hikes_old("shelf", raw_dir),
        records="hikes",
        key="id",
        ordered=True,
        stamps=("generated_at",),
        reads_raw_dir=True,
    ),
    "suggested_hikes_detail": Family(
        old=lambda raw_dir: _suggested_hikes_old("details", raw_dir),
        records="details",
        key="id",
        ordered=True,
        reads_raw_dir=True,
    ),
    "highlights": Family(old=_highlights_old, records="highlights", key="id", ordered=True, reads_raw_dir=True),
    # places.json, keyed by each place's `id`, in the file's order (kind, name,
    # id). `trailRadiusMiles` and `trailMilesMeasured`, beside the records, are
    # compared whole as top-level fields.
    "places": Family(old=_places_old, records="places", key="id", ordered=True, stamps=("generated_at",)),
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


# --- the challenges family (#1793, stage 3) ---------------------------------
#
# challenges.json, keyed by each challenge's id, in the files' path order. The
# old side reads what export_challenges.main() reads: the club folders and
# publishers.json in git, sources.json, the poi_<type>.geojson files
# export_poi.main() writes from the same raw layers, and trails.geojson's
# centerline from export_trails.main(), cut to decision 8's six decimals as
# the trails family cuts its old side, so both sides measure one line.

#: Why a challenge can be in today's file and not in the dbt writer's.
#: tests/test_dbt_challenges_parity.py holds the reason to a warehouse where
#: the two writers answer that way, so it cannot outlive its case.
CHALLENGE_REASONS = {
    "held_back": (
        "expected by rule 6 of pipeline/ELT.md's 'Who may publish': the club's folder (reference/challenges/<club>) "
        "has no sources.json row and no unregistered_publishing_sources row, so int_sources__publication holds it "
        "back, where export_challenges.py publishes the list as a labelled draft. The record the dbt models resolved "
        "for it (int_challenges__resolved) equals today's, field for field"
    ),
}


def _warehouse() -> Path:
    """The warehouse dbt built, where build_marts.py put it: OURHIKE_WAREHOUSE, else data/warehouse.duckdb."""
    import os

    return Path(os.environ.get("OURHIKE_WAREHOUSE") or Path(__file__).resolve().parent / "data" / "warehouse.duckdb")


def _challenges_old() -> dict:
    """export_challenges.build_output() over main()'s own inputs, dated today in UTC as main() dates it, which is
    the date the dbt build reads when the var challenges_build_date is unset. Each exporter's own lines go to a
    buffer, so the step prints the comparison and nothing else."""
    import contextlib
    import io
    import tempfile

    from shapely.geometry import shape

    import export_challenges
    import export_poi
    from export_nearby_trails import _rounded_geometry

    with contextlib.redirect_stdout(io.StringIO()):
        export_poi.NETWORK_LINES_PATH = _published_network()
        export_poi.main()
    trails = json.loads((_export_trails_run() / "trails.geojson").read_text(encoding="utf-8"))
    for feature in trails["features"]:
        feature["geometry"] = _rounded_geometry(shape(feature["geometry"]))
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "trails.geojson"
        path.write_text(json.dumps(trails), encoding="utf-8")
        centerline = export_challenges.load_centerline(path)
    pois = export_challenges.load_published_pois(export_poi.OUT_DIR)
    publishers = export_challenges.load_publishers()
    organizations = export_challenges.load_organizations()
    org_trails, _ = export_challenges.publisher_scope(publishers, organizations, pois)
    output, _ = export_challenges.build_output(
        export_challenges.load_challenge_files(),
        org_domains=export_challenges.publisher_domains(publishers, organizations, pois),
        org_trails=org_trails,
        organizations=organizations,
        pois=pois,
        centerline=centerline,
        today=datetime.now(timezone.utc).date(),
    )
    return json.loads(json.dumps(output))


def _resolved_challenge(row: dict) -> dict:
    """A row of int_challenges__resolved as pub_challenges writes it: that writer's json_object, field for field.
    A writer that changes its shape without this changing is a difference parity reports, never one it hides."""
    return {
        "id": row["challenge_id"],
        "org": row["org"],
        "trail": row["trail"],
        "name": row["name"],
        "status": row["status"],
        "summary": row["challenge_summary"],
        "window": {"opens": row["window_opens"], "closes": row["window_closes"]},
        "finish": None if row["finish_count"] is None else {"count": row["finish_count"], "label": row["finish_label"]},
        "reward": None
        if row["reward_kind"] is None
        else {"kind": row["reward_kind"], "rules_url": row["reward_rules_url"], "art": row["reward_art"]},
        "takes_entries": row["takes_entries"],
        "photo": row["photo"],
        "sections": json.loads(row["sections_published"]),
        "items": json.loads(row["items_published"]),
        "reviewed": row["reviewed"],
        "org_name": row["org_name"],
        "org_short": row["org_short"],
        "org_domain": row["org_domain"],
    }


RESOLVED_COLUMNS = (
    "challenge_id",
    "org",
    "trail",
    "name",
    "status",
    "challenge_summary",
    "window_opens",
    "window_closes",
    "finish_count",
    "finish_label",
    "reward_kind",
    "reward_rules_url",
    "reward_art",
    "takes_entries",
    "photo",
    "sections_published",
    "items_published",
    "reviewed",
    "org_name",
    "org_short",
    "org_domain",
)


def _held_back_reasons(old: dict, new: dict, warehouse: Path | None = None) -> dict[str, str]:
    """The challenges today's file publishes and the dbt writer's holds back, each explained only where the
    warehouse shows both halves: int_sources__publication does not let its source publish (no row for it is the
    case today, as the mart's inner join reads it), and int_challenges__resolved holds a record for it equal to
    today's. The order is explained when it is today's with those challenges left out. Anything else the new
    file lacks, adds or orders differently is still a difference."""
    import duckdb

    new_ids = [record["id"] for record in new.get("challenges") or []]
    missing = [record for record in old.get("challenges") or [] if record["id"] not in new_ids]
    if not missing:
        return {}
    # The columns _resolved_challenge() reads, by name: `select *` would fetch _loaded_at, and DuckDB converts a
    # timestamptz through pytz, which requirements.txt does not carry (measured on a venv of it alone).
    columns = ", ".join(f"resolved.{name}" for name in RESOLVED_COLUMNS)
    with duckdb.connect(str(warehouse or _warehouse()), read_only=True) as con:
        cursor = con.execute(
            f"select {columns}, coalesce(publication.may_publish, false) as may_publish"
            " from intermediate.int_challenges__resolved as resolved"
            " left join intermediate.int_sources__publication as publication"
            " on resolved.source_key = publication.source_key"
            " where resolved.problem is null"
        )
        names = [column[0] for column in cursor.description]
        resolved = {row["challenge_id"]: row for row in (dict(zip(names, values, strict=True)) for values in cursor.fetchall())}
    reasons: dict[str, str] = {}
    for record in missing:
        row = resolved.get(record["id"])
        if row is not None and not row["may_publish"] and canonical(_resolved_challenge(row)) == canonical(record):
            reasons[f"id {record['id']}"] = CHALLENGE_REASONS["held_back"]
    kept = [record["id"] for record in old.get("challenges") or [] if f"id {record['id']}" not in reasons]
    if reasons and kept == new_ids:
        reasons["order"] = CHALLENGE_REASONS["held_back"]
    return reasons


FAMILIES["challenges"] = Family(old=_challenges_old, records="challenges", key="id", ordered=True, explained=_held_back_reasons)


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


# --- the machine-readable result (--json-dir), for gate_report.py ------------

#: What a result file says it is, so gate_report.py refuses a JSON file in the
#: same directory that is not one, and a later change to the shape can say so.
RESULT_FORMAT = "ourhike-parity-result/1"

#: The fields that name where a record came from, at the record's top level or
#: under a GeoJSON feature's `properties`: a POI's `source` (atc_shelters), a
#: notice's `source_key` (atc_trail_updates), a closed line's `closure_source`
#: (the closure layer's registry key, export_nearby_trails.py). new_data_report.py
#: reads these counts to say which closure, warning, water and shelter sources
#: today's files already carry.
SOURCE_FIELDS = ("source_key", "source", "closure_source")

_ABSENT = object()


def _leaf_paths(value, path: str, found: set[str]) -> None:
    """Every field path inside `value`, lists of objects walked with `[]`."""
    if isinstance(value, dict) and value:
        for name, inner in value.items():
            _leaf_paths(inner, f"{path}.{name}" if path else name, found)
    elif isinstance(value, list) and value and all(isinstance(inner, dict) for inner in value):
        for inner in value:
            _leaf_paths(inner, f"{path}[]", found)
    else:
        found.add(path or "(the whole value)")


def _changed_paths(a, b, path: str, found: set[str]) -> None:
    if a is not _ABSENT and b is not _ABSENT and canonical(a) == canonical(b):
        return
    if a is _ABSENT or b is _ABSENT:
        _leaf_paths(b if a is _ABSENT else a, path, found)
    elif isinstance(a, dict) and isinstance(b, dict):
        for name in sorted(a.keys() | b.keys()):
            _changed_paths(a.get(name, _ABSENT), b.get(name, _ABSENT), f"{path}.{name}" if path else name, found)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for inner_a, inner_b in zip(a, b, strict=True):
            _changed_paths(inner_a, inner_b, f"{path}[]", found)
    else:
        found.add(path or "(the whole value)")


def changed_fields(what: str, old: str | None, new: str | None) -> list[str]:
    """The field paths one difference changes, from its two canonical sides (None for a side that lacks it).

    A record present on one side only changes every field it holds, so a POI
    the new path loses reads as losing its `properties.water_distance_ft`.
    Paths are dotted, with `[]` for a list's items (`geometry.coordinates[]`);
    a top-level field's paths start with its name; `order` is the record order.
    Compared as canonical JSON, as differences() compares, so 1 and 1.0 differ.
    """
    if what == "order":
        return ["order"]
    prefix = what.removeprefix("field ") if what.startswith("field ") else ""
    found: set[str] = set()
    _changed_paths(_ABSENT if old is None else json.loads(old), _ABSENT if new is None else json.loads(new), prefix, found)
    return sorted(found)


def _without(value, path: str):
    """`value` with the field at dotted `path` removed, where it is there."""
    head, _, rest = path.partition(".")
    if not isinstance(value, dict) or head not in value:
        return value
    if not rest:
        return {name: inner for name, inner in value.items() if name != head}
    return {**value, head: _without(value[head], rest)}


def rekeyed(found: list[tuple[str, str | None, str | None]], key: str) -> dict[str, str]:
    """{difference: its partner} for each record one side holds under one key and the other side under another.

    A record on one side only, whose every field but `key` equals a record on
    the other side only, is the same record under a new key (the network's
    TL05 ids are the first). Pairing them lets changed_fields() answer `key`
    for both, rather than every field each holds, so an id that moved does
    not read as a lost trail_status."""
    records = [(what, a, b) for what, a, b in found if what not in ("order", "file") and not what.startswith("field ")]
    waiting: dict[str, list[str]] = {}
    for what, a, b in records:
        if a is None and b is not None:
            waiting.setdefault(canonical(_without(json.loads(b), key)), []).append(what)
    pairs: dict[str, str] = {}
    for what, a, b in records:
        if b is None and a is not None:
            partners = waiting.get(canonical(_without(json.loads(a), key)))
            if partners:
                partner = partners.pop(0)
                pairs[what], pairs[partner] = partner, what
    return pairs


def record_sources(document: dict | None, records: str) -> tuple[dict[str, int], int]:
    """({source value: records naming it}, records naming none), over `document[records]`, by SOURCE_FIELDS."""
    counts: dict[str, int] = {}
    unnamed = 0
    for record in (document or {}).get(records) or []:
        holders = [record] if isinstance(record, dict) else []
        if holders and isinstance(record.get("properties"), dict):
            holders.append(record["properties"])
        named = {
            holder[name] for holder in holders for name in SOURCE_FIELDS if isinstance(holder.get(name), str) and holder[name]
        }
        for value in named:
            counts[value] = counts.get(value, 0) + 1
        unnamed += not named
    return dict(sorted(counts.items())), unnamed


def result_document(
    name: str,
    family: Family,
    new_file: Path,
    outcome: str,
    exit_code: int,
    *,
    old: dict | None = None,
    new: dict | None = None,
    found: list[tuple[str, str | None, str | None]] = (),
    reasons: dict[str, str] | None = None,
    message: str | None = None,
) -> dict:
    """One family's comparison as RESULT_FORMAT: everything the console said, in fields.

    `outcome` is one of `no_differences`, `differences` (exit 1), `neither_writes`
    (two absent files, which agree), `one_side_writes` (exit 1) and
    `old_side_refused` (today's builder raised, so nothing was compared).
    `explained` holds the differences `family.explained` accounts for, each
    with its reason, and `differences` every other one; both carry the
    changed field paths, which gate_report.py ranks safety fields first by.
    A record that only changed its key (rekeyed()) changes `family.key`
    alone, and names its partner in `same_record_as`.
    """
    reasons = reasons or {}
    partners = rekeyed(list(found), family.key)

    def entry(what: str, a: str | None, b: str | None) -> dict:
        if what in partners:
            return {"what": what, "old": a, "new": b, "fields": [family.key], "same_record_as": partners[what]}
        return {"what": what, "old": a, "new": b, "fields": changed_fields(what, a, b)}

    old_sources, old_unnamed = record_sources(old, family.records)
    new_sources, new_unnamed = record_sources(new, family.records)
    return {
        "format": RESULT_FORMAT,
        "family": name,
        "new_file": str(new_file),
        "new_file_name": new_file.name,
        "records": family.records,
        "key": family.key,
        "ordered": family.ordered,
        "compared_by_form_only": list(family.stamps),
        "dropped_before_comparing": list(family.volatile),
        "outcome": outcome,
        "exit_code": exit_code,
        "message": message,
        "old_records": None if old is None else len(old.get(family.records) or []),
        "new_records": None if new is None else len(new.get(family.records) or []),
        "explained": [{**entry(what, a, b), "reason": reasons[what]} for what, a, b in found if what in reasons],
        "differences": [entry(what, a, b) for what, a, b in found if what not in reasons],
        "old_sources": old_sources,
        "old_records_naming_no_source": old_unnamed,
        "new_sources": new_sources,
        "new_records_naming_no_source": new_unnamed,
    }


def write_result(json_dir: Path, document: dict) -> Path:
    """`document` as `<json_dir>/<family>.json`, the directory made if need be."""
    json_dir.mkdir(parents=True, exist_ok=True)
    path = json_dir / f"{document['family']}.json"
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("family", choices=sorted(FAMILIES))
    parser.add_argument("--new", type=Path, required=True, help="the file the family's pub_ writer wrote")
    parser.add_argument(
        "--raw-dir", type=Path, default=Path("data/raw"), help="make_dbt_fixtures.py's files, for a family built from them"
    )
    parser.add_argument(
        "--warehouse", type=Path, default=Path("data/warehouse.duckdb"), help="the built warehouse, for a family read from it"
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=None,
        help="also write the result as <dir>/<family>.json, for gate_report.py; the console and exit code are unchanged",
    )
    args = parser.parse_args(argv)

    family = FAMILIES[args.family]

    def finish(exit_code: int, outcome: str, **fields) -> int:
        if args.json_dir is not None:
            write_result(args.json_dir, result_document(args.family, family, args.new, outcome, exit_code, **fields))
        return exit_code

    try:
        if family.reads_warehouse:
            old = family.old(args.raw_dir, args.warehouse)
        elif family.reads_raw_dir:
            old = family.old(args.raw_dir)
        else:
            old = family.old()
    except SystemExit as refusal:
        # Some builders refuse rather than publish less (a reviewed file with
        # a row problem publishes nothing); the exit is theirs, unchanged.
        finish(refusal.code if isinstance(refusal.code, int) else 1, "old_side_refused", message=str(refusal.code))
        raise
    if old is None or not args.new.exists():
        # An exporter that writes no file on some runs answers None then, as
        # export_suggested_hikes.py's does when no hike ships, and its writer
        # writes none either (phone_file's when_empty: keep_last_file). Two
        # absent files agree; one beside none is the difference.
        if old is None and not args.new.exists():
            print(f"{args.family}: neither today's exporter nor the writer writes a file this run")
            return finish(0, "neither_writes", message="neither today's exporter nor the writer writes a file this run")
        exporter = "writes no file" if old is None else "writes one"
        writer = f"wrote {args.new}" if args.new.exists() else "wrote none"
        print(f"{args.family}: 1 difference(s):\n  today's exporter {exporter}, and the writer {writer}")
        # One difference, the whole file. Where today's exporter is the side
        # that wrote, its records are what the new path loses, so every field
        # they hold reads as changed (changed_fields()).
        lost = canonical((old or {}).get(family.records) or []) if old is not None else None
        return finish(
            1,
            "one_side_writes",
            old=old,
            found=[("file", lost, None if old is not None else canonical(str(args.new)))],
            message=f"today's exporter {exporter}, and the writer {writer}",
        )
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
    unexplained = [difference for difference in found if difference[0] not in reasons]
    if not unexplained:
        beyond = f" beyond the {len(explained)} explained above" if explained else ""
        print(f"{args.family}: no differences{beyond} across {count} {family.records}, keyed by {family.key}")
        return finish(0, "no_differences", old=old, new=new, found=found, reasons=reasons)
    print(f"{args.family}: {len(unexplained)} difference(s):")
    for what, a, b in unexplained:
        print(f"  {what}\n    old: {a}\n    new: {b}")
    return finish(1, "differences", old=old, new=new, found=found, reasons=reasons)


if __name__ == "__main__":
    sys.exit(main())
