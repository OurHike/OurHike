"""The places family's SQL answers what export_places.py answers, on the same rows (#1793, stage 3).

places.json moved to SQL (pipeline/ELT.md's places rows, PL01-PL11), and until
stage 5 deletes the Python both are live. parity.py compares the two files on
the fixture warehouse in CI; this holds the cases the fixture never reaches,
one dbt unit test per case of tests/test_export_places.py:

- every case there is a unit test of the same name (`places_<case>`), or one
  of the two that stay Python because publish.py and the manifest do
  (STAYS_PYTHON);
- each unit test on int_places__park_units, int_places__lines,
  int_places__point_places and int_places__resolved has its given rows
  written out as the files export_places.py reads, and load_parks(),
  load_lines(), load_point_places() or build_output() answers what the unit
  test expects;
- each unit test on int_places__waypoints has its points_of_interest rows
  written by export_poi.py's own write_poi_type() and as nearby_poi.geojson,
  and read back as load_point_places() reads them: the order, and lon and
  lat exactly as GDAL prints them, which dbt checks only to one decimal;
- each unit test on pub_places builds its document from the same rows with
  export_places.py's own _record();
- the state codes, the radius and the long-trail threshold are
  export_places.py's constants.

Nothing here is a deliberate difference: on every unit test's rows the SQL
and the Python agree (DELIBERATE is empty, and test_deliberate_differences
keeps it honest).
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest
import shapely.wkt
import yaml
from pyproj import Geod, Transformer
from shapely.geometry import mapping
from shapely.ops import transform as shapely_transform

import export_places as exporter
from export_nearby_trails import NAMED_TRAIL_THRESHOLD_MILES, owned_route_names, shipped_line_source_keys
from lib.source_registry import POI_SOURCE_KEYS
from tests.test_dbt_trail_network_parity import _geodesic_length_sql

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "places" / "_places__unit_tests.yml"
WRITER = DBT / "models" / "publish" / "_publish__places.yml"
POINT_PLACES = DBT / "models" / "intermediate" / "places" / "int_places__point_places.sql"
EXPORTER_TESTS = Path(__file__).parent / "test_export_places.py"

WHEN = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
STAMP = "2026-09-10T12:00:00Z"

#: The cases of test_export_places.py that test publish.py and the manifest,
#: which stay Python ("Not dbt: the manifest", pipeline/ELT.md).
STAYS_PYTHON = {
    "test_the_manifest_hashes_the_file_it_points_at",
    "test_publish_collects_it_only_when_the_exporter_wrote_one",
}

#: Unit tests whose SQL answers differently from the Python on purpose, each
#: with its reason. None: every unit test's rows agree.
DELIBERATE: dict[str, str] = {}

#: The kind places.json gives a published POI type, and back.
KIND_OF_TYPE = exporter.POINT_PLACE_KINDS
TYPE_OF_KIND = {kind: poi_type for poi_type, kind in KIND_OF_TYPE.items()}


# --- reading the unit tests -------------------------------------------------


def unit_tests(model: str | None = None) -> list[dict]:
    tests = yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"] + (yaml.safe_load(WRITER.read_text()).get("unit_tests") or [])
    return [test for test in tests if model is None or test["model"] == model]


VALUES = re.compile(r"from \(values(.*)\)\s*as\s+\w+\s*\(([^)]*)\)", re.S)


def given(test: dict, model: str) -> list[dict]:
    """The rows a unit test gives `model`: its dict rows, or the VALUES list of a `format: sql` block."""
    found = [item for item in test["given"] if item["input"] == f"ref('{model}')"]
    if not found:
        return []
    item = found[0]
    if item.get("format") != "sql":
        return item.get("rows") or []
    match = VALUES.search(item["rows"])
    assert match, f"{test['name']}: a format sql input here is written as `from (values ...) as name (columns)`"
    body = re.sub(r"\bnull\b", "None", match.group(1))
    body = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", body))
    columns = [column.strip() for column in match.group(2).split(",")]
    rows = ast.literal_eval(f"[{body}]")
    return [dict(zip(columns, row if isinstance(row, tuple) else (row,), strict=True)) for row in rows]


def radius_of(test: dict) -> float:
    return ((test.get("overrides") or {}).get("vars") or {}).get("places_trail_radius_miles", exporter.PLACE_TRAIL_RADIUS_MILES)


# --- writing the rows out as the files export_places.py reads ---------------


def collection(features: list[dict]) -> str:
    return json.dumps({"type": "FeatureCollection", "features": features})


def feature(geometry: dict | None, properties: dict) -> dict:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def geometry_of_wkt(wkt: str | None) -> dict | None:
    return None if wkt is None else json.loads(json.dumps(mapping(shapely.wkt.loads(wkt))))


def dlt_name(field: str) -> str:
    """dlt's sql_ci_v1 for a field name, as int_places__park_units spells it in SQL."""
    step = re.sub(r"[^a-zA-Z0-9_]+", "_", field.strip())
    step = f"_{step}" if re.match(r"[0-9]", step) else step
    step = step if step == "_" else step.rstrip("_")
    return re.sub(r"__+", "_", step).lower()


def registry_of(test: dict) -> dict:
    """sources.json as a unit test's registry, publication and organization rows give it.

    may_publish stands in for reaches_hikers, as int_sources__publication's
    does for every registered source (64 of 64 agree, measured 2026-10-02).
    """
    publication = {row["source_key"]: bool(row["may_publish"]) for row in given(test, "int_sources__publication")}
    sources = []
    for row in given(test, "stg_registry__sources"):
        entry = {"key": row["source_key"], **json.loads(row.get("entry") or "{}")}
        if row.get("provider") is not None:
            entry.setdefault("provider", row["provider"])
        if row["source_key"] in publication:
            entry["reaches_hikers"] = publication[row["source_key"]]
        sources.append(entry)
    orgs = {
        row["steward_id"]: {"provider": row["provider"], **({"state": row["org_state"]} if row.get("org_state") else {})}
        for row in given(test, "stg_registry__organizations")
    }
    return {"sources": sources, "organizations": {"orgs": orgs}}


def park_layer(test: dict, registry: dict) -> str:
    """The park layer's file from base_oprhp__park_polygons' rows: each declared field under its own spelling."""
    entry = exporter.find_source(registry, exporter.PARKS_KEY) or {}
    fields = [entry.get(role, default) for role, default in exporter.PARK_FIELDS.items()] + [exporter.PARK_CATEGORY_FIELD]
    features = []
    for row in sorted(given(test, "base_oprhp__park_polygons"), key=lambda row: row["source_row"]):
        properties = {field: row[dlt_name(field)] for field in fields if field and dlt_name(field) in row}
        features.append(feature(geometry_of_wkt(row.get("geom", row.get("geom_wkt"))), properties))
    return collection(features)


def line_files(network: list[dict], at_lines: list[dict]) -> tuple[str, str]:
    """nearby_trails.geojson and trails.geojson from lines rows: each line's `source`, `name` and geometry."""

    def lines(rows):
        return collection(
            [feature(json.loads(row["geom_geojson"]), {"source": row["source_key"], "name": row["name"]}) for row in rows]
        )

    return lines(network), lines(at_lines)


def write_inputs(tmp_path: Path, parks: str = "", nearby_poi: str = "", communities: str = "", lines=("", "")) -> dict:
    """The five files build_output() reads, under tmp_path; an empty string writes no file."""
    paths = {
        "parks": tmp_path / "raw" / "external" / f"{exporter.PARKS_KEY}.geojson",
        "poi_dir": tmp_path / "processed" / "poi",
        "nearby": tmp_path / "processed" / "nearby_poi.geojson",
        "communities": tmp_path / "raw" / exporter.COMMUNITIES_RAW,
        "lines": [tmp_path / "processed" / name for name in exporter.LINE_ARTIFACTS],
    }
    paths["poi_dir"].mkdir(parents=True, exist_ok=True)
    for path, text in ((paths["parks"], parks), (paths["nearby"], nearby_poi), (paths["communities"], communities)):
        if text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    for path, text in zip(paths["lines"], lines, strict=True):
        if text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    return paths


def spatial() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


# --- the Python's answer for each model's unit test ------------------------


def python_park_units(test: dict, tmp_path: Path) -> list[dict]:
    """load_parks() over the unit test's polygons, each unit with its geometry as measure() unions it."""
    registry = registry_of(test)
    paths = write_inputs(tmp_path, parks=park_layer(test, registry) if given(test, "base_oprhp__park_polygons") else "")
    con = spatial()
    parks, _ = exporter.load_parks(con, paths["parks"], registry)
    exporter.measure(con, parks, [], exporter.PLACE_TRAIL_RADIUS_MILES, False)
    shapes = dict(con.execute("SELECT idx, ST_AsText(geom) FROM park").fetchall()) if parks else {}
    return [
        {
            "place_id": park["id"],
            "name": park["name"],
            "category": park["category"],
            "state": park["state"],
            "unit_order": index,
            "polygons": len(park["parts"]),
            "park_wkt": shapes.get(index),
        }
        for index, park in enumerate(parks)
    ]


def python_lines(test: dict, tmp_path: Path) -> list[dict]:
    """load_lines() over the unit test's trail_lines rows, with the name load_named_trails() sums each under.

    Each row goes in the file its `line_kind` says draws it: a `network` line in
    nearby_trails.geojson, the A.T.'s centerline, side trails and spurs in
    trails.geojson."""
    registry = registry_of(test)
    rows = given(test, "trail_lines")
    network = [row for row in rows if row["line_kind"] == "network"]
    at_lines = [row for row in rows if row["line_kind"] != "network"]
    paths = write_inputs(tmp_path, lines=line_files(network, at_lines))
    con = spatial()
    exporter.load_lines(con, paths["lines"], shipped_line_source_keys(registry))
    owned = next((name for name, owner in owned_route_names(registry).items() if owner == exporter.AT_SOURCE), None)
    kept = con.execute("SELECT source, name FROM lines").fetchall()
    return [
        {"source_key": source, "name": name, "trail_name": owned if source == exporter.AT_SOURCE and owned else name}
        for source, name in kept
    ]


def python_waypoints(test: dict, tmp_path: Path) -> list[dict]:
    """The waypoints load_point_places() reads, in its order, from the unit test's points_of_interest rows.

    The rows are written as today's writers write the four files: each
    poi_<type>.geojson by export_poi.py's own write_poi_type(), through GDAL,
    whose printing of lon and lat is what a phone reads back, and
    nearby_poi.geojson with json.dumps, as export_nearby_poi.py writes it,
    each file in record order. They are read back by
    export_spurs.load_destination_pois() in POINT_PLACE_KINDS order, as
    load_point_places() reads them, then nearby_poi.geojson's waypoint types.
    retired_poi rows are written nowhere, because nothing here reads that
    file."""
    import export_poi
    from export_spurs import load_destination_pois, load_features

    rows = given(test, "points_of_interest")

    def in_file(phone_files: str) -> list[dict]:
        return sorted((row for row in rows if row["phone_files"] == phone_files), key=lambda row: row["record_order"])

    poi_dir = tmp_path / "poi"
    con = spatial()
    original = export_poi.OUT_DIR
    export_poi.OUT_DIR = poi_dir
    try:
        for poi_type in KIND_OF_TYPE:
            records = [
                {
                    "id": row["poi_id"],
                    "poi_type": poi_type,
                    "trail_id": None,
                    "source": row["source"],
                    "source_feature_id": row["source_feature_id"],
                    "name": row["name"],
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "confidence": None,
                }
                for row in in_file("poi_by_type")
                if row["poi_type"] == poi_type
            ]
            export_poi.write_poi_type(con, poi_type, records)
    finally:
        export_poi.OUT_DIR = original
    nearby = collection(
        [
            feature(
                {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                {name: row[name] for name in ("poi_type", "source", "source_feature_id", "name", "lat", "lon")}
                | {"id": row["poi_id"]},
            )
            for row in in_file("nearby_poi")
        ]
    )
    paths = write_inputs(tmp_path, nearby_poi=nearby)
    nearby_rows = [feature.get("properties") or {} for feature in load_features(paths["nearby"])]
    read = [*load_destination_pois(poi_dir, KIND_OF_TYPE), *nearby_rows]
    by_id = {row["poi_id"]: row for row in rows}
    return [
        {
            "poi_id": properties["id"],
            "poi_type": properties["poi_type"],
            "source": properties["source"],
            "source_key": by_id[properties["id"]]["source_key"],
            "source_feature_id": properties["source_feature_id"],
            "name": properties["name"],
            "lon": properties["lon"],
            "lat": properties["lat"],
            "waypoint_order": order,
        }
        for order, properties in enumerate(row for row in read if row.get("poi_type") in KIND_OF_TYPE)
    ]


def python_point_places(test: dict, tmp_path: Path) -> list[dict]:
    """load_point_places() over the unit test's waypoints, in waypoint order, and its Communities rows."""
    registry = registry_of(test)
    waypoints = sorted(given(test, "int_places__waypoints"), key=lambda row: row["waypoint_order"])
    nearby = collection(
        [
            feature(
                {"type": "Point", "coordinates": [row["lon"], row["lat"]]} if row["lon"] is not None else None,
                {
                    "id": row["poi_id"],
                    "poi_type": row["poi_type"],
                    "source": row["source"],
                    "name": row["name"],
                    "lon": row["lon"],
                    "lat": row["lat"],
                    "source_feature_id": row["source_feature_id"],
                },
            )
            for row in waypoints
        ]
    )
    communities = collection(
        [
            feature({"type": "Point", "coordinates": [0, 0]}, {"GlobalID": row["globalid"], "STATE": row["state"]})
            for row in given(test, "stg_atc__communities")
        ]
    )
    paths = write_inputs(tmp_path, nearby_poi=nearby, communities=communities)
    places = exporter.load_point_places(
        registry, paths["poi_dir"], paths["nearby"], exporter.community_states(paths["communities"])
    )
    return [
        {
            "place_id": place["id"],
            "poi_id": place["poiId"],
            "name": place["name"],
            "kind": place["kind"],
            "state": place["state"],
            "source": place["source"],
            "lon": place["lon"],
            "lat": place["lat"],
        }
        for place in places
    ]


def resolved_inputs(test: dict, tmp_path: Path) -> tuple[dict, dict]:
    """build_output()'s registry and files for int_places__resolved's given rows.

    A park unit is one polygon whose unit id is its place id's tail, written
    in unit_order, so load_parks() gives it the same id, name and place in
    the list; its state is its organization's. A point is a nearby_poi.geojson
    feature whose source's organization declares the point's state, its
    source a town layer for a town. A line is a feature of the file its kind
    is drawn in, a network source shipping and the centerline owning the
    route name its lines are summed under.
    """
    parks = sorted(given(test, "int_places__park_units"), key=lambda row: row["unit_order"])
    points = sorted(given(test, "int_places__point_places"), key=lambda row: row["waypoint_order"])
    lines = given(test, "int_places__lines")

    park_states = {row["state"] for row in parks}
    assert len(park_states) <= 1, "one organization publishes the park layer, so one state"
    orgs = {
        "org:parks": {
            "provider": "NYS OPRHP",
            **({"state": park_states.pop()} if park_states and None not in park_states else {}),
        }
    }
    sources = [{"key": exporter.PARKS_KEY, "provider": "NYS OPRHP", "reaches_hikers": True, **exporter.PARK_FIELDS}]
    for row in points:
        key = POI_SOURCE_KEYS.get(row["source"], row["source"])
        provider = f"provider for {row['state']}"
        if row["state"] is not None:
            orgs[f"org:{row['state']}"] = {"provider": provider, "state": row["state"]}
        if not any(source["key"] == key for source in sources):
            sources.append({"key": key, "provider": provider, **({"place_kind": "town"} if row["kind"] == "town" else {})})
    for row in lines:
        if row["source_key"] == exporter.AT_SOURCE:
            continue
        if not any(source["key"] == row["source_key"] for source in sources):
            sources.append(
                {"key": row["source_key"], "kind": "external_arcgis_layer", "blaze_default": "Red", "reaches_hikers": True}
            )
    owned = sorted(
        {row["trail_name"] for row in lines if row["source_key"] == exporter.AT_SOURCE and row["trail_name"] != row["name"]}
    )
    sources.append(
        {"key": exporter.AT_SOURCE, "provider": "ATC", "reaches_hikers": True, **({"owns_route_names": owned} if owned else {})}
    )
    registry = {"sources": sources, "organizations": {"orgs": orgs}}

    def unit_of(place_id: str) -> str:
        return place_id.split(":", 1)[1]

    park_features = [
        feature(
            geometry_of_wkt(row["park_wkt"]),
            {
                "GlobalID": f"gid-{index}",
                "Name": row["name"],
                "MasterAreaID": unit_of(row["place_id"]),
                "Category": row["category"],
            },
        )
        for index, row in enumerate(parks)
    ]
    nearby = [
        feature(
            {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            {
                "id": row["poi_id"],
                "poi_type": TYPE_OF_KIND[row["kind"]],
                "source": row["source"],
                "name": row["name"],
                "lon": row["lon"],
                "lat": row["lat"],
            },
        )
        for row in points
    ]
    network = [row for row in lines if row["source_key"] != exporter.AT_SOURCE]
    at_lines = [row for row in lines if row["source_key"] == exporter.AT_SOURCE]
    paths = write_inputs(
        tmp_path,
        parks=collection(park_features) if parks else "",
        nearby_poi=collection(nearby) if points else "",
        lines=line_files(network, at_lines) if lines else ("", ""),
    )
    return registry, paths


def python_resolved(test: dict, tmp_path: Path) -> tuple[list[dict], bool]:
    """build_output()'s places and trailMilesMeasured for int_places__resolved's given rows."""
    registry, paths = resolved_inputs(test, tmp_path)
    output, _ = exporter.build_output(
        registry,
        paths["parks"],
        paths["poi_dir"],
        paths["nearby"],
        paths["communities"],
        paths["lines"],
        WHEN,
        radius_miles=radius_of(test),
    )
    return output["places"], output["trailMilesMeasured"]


def record_of(row: dict) -> dict:
    """The places.json record a resolved row publishes, its JSON-text numbers read back."""
    numbers = {
        name: json.loads(row[name]) if row.get(name) is not None else None for name in ("lon", "lat", "bbox", "trail_miles")
    }
    record = {
        "id": row["place_id"],
        "poiId": row.get("poi_id"),
        "name": row["name"],
        "kind": row["kind"],
        "category": row.get("category"),
        "state": row.get("state"),
        "within": row.get("within_park"),
        "lon": numbers["lon"],
        "lat": numbers["lat"],
        "bbox": numbers["bbox"],
        "trailMiles": numbers["trail_miles"],
        "source": row["source"],
    }
    return {name: value for name, value in record.items() if value is not None}


# --- the tests --------------------------------------------------------------


def _ids(tests):
    return [test["name"] for test in tests]


def test_every_export_places_case_is_a_unit_test_or_stays_python():
    cases = set(re.findall(r"^    def (test_\w+)\(", EXPORTER_TESTS.read_text(), re.M))
    named = {test["name"].removeprefix("places_") for test in unit_tests()}
    missing = {case for case in cases - STAYS_PYTHON if case.removeprefix("test_") not in named}
    assert len(cases) == 34, "test_export_places.py's 34 cases, as pipeline/ELT.md's places row counts them"
    assert missing == set(), f"no unit test mirrors {sorted(missing)}"


def test_deliberate_differences_name_unit_tests_that_exist():
    names = {test["name"] for test in unit_tests()}
    assert set(DELIBERATE) <= names


def test_the_state_codes_are_us_state_codes():
    text = POINT_PLACES.read_text()
    block = re.search(r"state_codes \(state_name, state_code\) as \(\s*values(.*?)\n\),", text, re.S).group(1)
    pairs = dict(re.findall(r"\('([a-z ]+)', '([A-Z]{2})'\)", block))
    assert pairs == exporter.US_STATE_CODES


def test_the_radius_and_the_threshold_are_export_places_own():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["places_trail_radius_miles"] == exporter.PLACE_TRAIL_RADIUS_MILES
    assert variables["trail_lines_network_named_trail_threshold_miles"] == NAMED_TRAIL_THRESHOLD_MILES


@pytest.mark.parametrize("test", unit_tests("int_places__park_units"), ids=_ids(unit_tests("int_places__park_units")))
def test_park_units_answer_what_load_parks_answers(test, tmp_path):
    python = python_park_units(test, tmp_path)
    expected = test["expect"]["rows"]
    assert len(python) == len(expected), test["name"]
    for got, want in zip(python, expected, strict=True):
        for name, value in want.items():
            if name == "park_wkt":
                con = spatial()
                same = con.execute("SELECT ST_Equals(ST_GeomFromText(?), ST_GeomFromText(?))", [got[name], value]).fetchone()[0]
                assert same, f"{test['name']}: {got[name]} is not {value}"
            else:
                assert got[name] == value, f"{test['name']}: {name} {got[name]!r}, SQL {value!r}"


@pytest.mark.parametrize("test", unit_tests("int_places__lines"), ids=_ids(unit_tests("int_places__lines")))
def test_lines_answer_what_load_lines_answers(test, tmp_path):
    def key(row):
        return (row["source_key"], row["name"] or "", row["trail_name"] or "")

    python = sorted(python_lines(test, tmp_path), key=key)
    expected = sorted(
        ({name: row.get(name) for name in ("source_key", "name", "trail_name")} for row in test["expect"]["rows"]), key=key
    )
    assert python == expected, test["name"]


@pytest.mark.parametrize("test", unit_tests("int_places__waypoints"), ids=_ids(unit_tests("int_places__waypoints")))
def test_waypoints_are_what_load_point_places_reads_off_the_files(test, tmp_path):
    """Every column exactly, lon and lat included, where dbt's own comparison of a DOUBLE stops at one decimal."""
    assert python_waypoints(test, tmp_path) == test["expect"]["rows"], test["name"]


@pytest.mark.parametrize("test", unit_tests("int_places__point_places"), ids=_ids(unit_tests("int_places__point_places")))
def test_point_places_answer_what_load_point_places_answers(test, tmp_path):
    python = python_point_places(test, tmp_path)
    expected = test["expect"]["rows"]
    assert [row["place_id"] for row in python] == [row["place_id"] for row in expected], test["name"]
    for got, want in zip(python, expected, strict=True):
        shared = [name for name in want if name in got]
        assert {name: got[name] for name in shared} == {name: want[name] for name in shared}, test["name"]


@pytest.mark.parametrize("test", unit_tests("int_places__resolved"), ids=_ids(unit_tests("int_places__resolved")))
def test_resolved_answers_what_build_output_answers(test, tmp_path):
    places, measured = python_resolved(test, tmp_path)
    expected = sorted(test["expect"]["rows"], key=lambda row: row["place_order"])
    assert places == [record_of(row) for row in expected], test["name"]
    assert all(row["trail_miles_measured"] == measured for row in expected), test["name"]


@pytest.mark.parametrize("test", unit_tests("pub_places"), ids=_ids(unit_tests("pub_places")))
def test_the_writer_writes_what_record_writes(test):
    places = sorted(given(test, "places"), key=lambda row: row["place_order"])
    measured = bool(given(test, "int_places__lines"))
    python = {
        "generated_at": STAMP,
        "trailRadiusMiles": radius_of(test),
        "trailMilesMeasured": measured,
        "places": [
            exporter._record(
                {
                    "id": row["place_id"],
                    "poiId": row.get("poi_id"),
                    "name": row["name"],
                    "kind": row["kind"],
                    "category": row.get("category"),
                    "state": row.get("state"),
                    "within": row.get("within_park"),
                    "lon": row["lon"],
                    "lat": row["lat"],
                    "bbox": row.get("bbox"),
                    "trailMiles": row.get("trail_miles"),
                    "source": row["source"],
                }
            )
            for row in places
        ],
    }
    (row,) = test["expect"]["rows"]
    written = row["places_document"]
    assert json.loads(written) == python, test["name"]
    assert list(json.loads(written)) == list(python), "the document's fields in build_output()'s order"
    for record in json.loads(written)["places"]:
        assert None not in record.values()


def test_a_place_from_a_layer_no_exporter_reads_is_explained_as_decision_31s_new_data():
    """places' parity explains a trailhead or parking lot from one of decision 54's wave 1 point layers as new data,
    and the order with those places left out. A place from a layer export_nearby_poi.py reads, or one with no source,
    is still a difference, and so is an order that differs once the new places are left out."""
    import parity

    shared = {"id": "dec_parking_areas:100", "source": "dec_parking_areas", "kind": "parking"}
    town = {"id": "atc_communities:community-0", "kind": "town"}
    old = {"places": [shared, town]}
    club = {"id": "amc_net_parking:5631", "source": "amc_net_parking", "kind": "parking"}
    today_layer = {"id": "dec_parking_areas:101", "source": "dec_parking_areas", "kind": "parking"}
    sourceless = {"id": "trail:somewhere", "kind": "trailhead"}
    new = {"places": [shared, club, today_layer, sourceless, town]}

    reasons = parity._places_reasons(old, new)

    assert set(reasons) == {"id amc_net_parking:5631"}
    assert reasons["id amc_net_parking:5631"].startswith(parity.NEW_DATA_REASON)
    # Only the new layer's place added: the order with it left out is today's, so the order is explained too.
    assert parity._places_reasons(old, {"places": [shared, club, town]}) == {
        "id amc_net_parking:5631": parity.PLACES_REASONS["new_source"],
        "order": parity.PLACES_REASONS["new_source"],
    }
    # Today's places reordered: the order stays a difference.
    assert "order" not in parity._places_reasons(old, {"places": [town, club, shared]})


def test_a_park_from_a_club_places_layer_is_explained_as_decision_31s_new_data_by_its_own_reason():
    """A club places layer's park (int_places__club_units) is new data too, and parity names it as a places layer's
    rather than in the words it uses for a point layer's trailhead."""
    import parity

    shared = {"id": "dec_parking_areas:100", "source": "dec_parking_areas", "kind": "parking"}
    park = {"id": "dcnr_state_park_boundaries:k-1", "source": "dcnr_state_park_boundaries", "kind": "park"}

    reasons = parity._places_reasons({"places": [shared]}, {"places": [park, shared]})

    assert reasons["id dcnr_state_park_boundaries:k-1"] == parity.PLACES_REASONS["club_places"]
    assert reasons["id dcnr_state_park_boundaries:k-1"].startswith(parity.NEW_DATA_REASON)
    assert "dcnr_state_park_boundaries" in parity._club_places_sources()
    assert "usgs_gnis_populated_places" in parity._club_places_sources()


def test_a_long_trail_whose_copied_line_today_measures_twice_is_explained_by_decision_40_and_nothing_else(tmp_path, monkeypatch):
    """Monthly run 30's trail:alaska_trails:Haessler-Norris Sled Dog: today's network file draws one of the trail's
    lines twice, and today's trailMiles counts it twice. Only a `trail:` place that differs in trailMiles alone, today's
    figure the miles over every line and the dbt writer's the miles over each geometry once, is explained."""
    import parity

    name = "Haessler-Norris Sled Dog"
    copied, other = [[-149.9, 61.2], [-149.9, 61.21]], [[-149.8, 61.2], [-149.8, 61.3]]

    def line(line_id: str, coordinates: list) -> dict:
        return {
            "type": "Feature",
            "properties": {"id": line_id, "source": "alaska_trails", "name": name},
            "geometry": {"type": "LineString", "coordinates": coordinates},
        }

    network = tmp_path / "nearby_trails.geojson"
    lines = [line("alaska_trails:1", copied), line("alaska_trails:2", copied), line("alaska_trails:3", other)]
    network.write_text(json.dumps({"type": "FeatureCollection", "features": lines}))
    monkeypatch.setattr(parity, "_published_network", lambda: network)
    geod = Geod(ellps="WGS84")
    copied_miles, other_miles = (geod.line_length(*zip(*coordinates)) / 1609.344 for coordinates in (copied, other))
    every, once = round(2 * copied_miles + other_miles, 1), round(copied_miles + other_miles, 1)
    assert every != once

    def place(trail_miles: float, **changed) -> dict:
        record = {"id": f"trail:alaska_trails:{name}", "name": name, "kind": "trail", "source": "alaska_trails"}
        return {**record, "trailMiles": trail_miles, **changed}

    today = {"places": [place(every)]}

    assert parity._places_reasons(today, {"places": [place(once)]}) == {
        f"id trail:alaska_trails:{name}": parity.PLACES_COPY_REASON
    }
    # A figure the copy does not account for, or another field changed beside it, is still a difference.
    assert parity._places_reasons(today, {"places": [place(round(once - 0.5, 1))]}) == {}
    assert parity._places_reasons(today, {"places": [place(once, lat=61.25)]}) == {}


# --- the measure both sides use (decision 97) ---------------------------------


def test_export_places_measures_with_the_macro_int_places_resolved_uses():
    """export_places._geodesic_metres writes out macros/geodesic_length_m.sql, which int_places__resolved measures a
    piece with, as one text: the parity above then rests on the two sides running one expression."""

    def spelled(sql: str) -> str:
        return " ".join(sql.lower().replace("(", " ( ").replace(")", " ) ").replace(",", " , ").split())

    assert spelled(exporter._geodesic_metres("piece")) == spelled(_geodesic_length_sql("piece"))


# A north-south line, each end placed with pyproj's Geod fwd, and a park box
# that holds all of it or cuts it short. EPSG:5070 reads the whole Anchorage
# line 4.44 miles and the Harriman one 5.04 (pyproj, 2026-10-06).
CUT_PIECES = {
    "a line inside a park at Anchorage, Alaska": (
        "LINESTRING (-149.9 61.2, -149.9 61.27221126419307)",
        "POLYGON ((-150.0 61.15, -149.8 61.15, -149.8 61.35, -150.0 61.35, -150.0 61.15))",
    ),
    "a line the park's edge cuts at Anchorage, Alaska": (
        "LINESTRING (-149.9 61.2, -149.9 61.27221126419307)",
        "POLYGON ((-150.0 61.15, -149.8 61.15, -149.8 61.25, -150.0 61.25, -150.0 61.15))",
    ),
    "a line the park's edge cuts at Harriman, New York": (
        "LINESTRING (-74.1 41.25, -74.1 41.32245417114151)",
        "POLYGON ((-74.2 41.2, -74.0 41.2, -74.0 41.3, -74.2 41.3, -74.2 41.2))",
    ),
}


@pytest.mark.parametrize(("line_wkt", "park_wkt"), CUT_PIECES.values(), ids=CUT_PIECES.keys())
def test_a_piece_a_park_cuts_measures_pyprojs_geodesic_length(line_wkt, park_wkt):
    """The piece int_places__resolved and export_places.measure() take a park's miles from: the line cut against the
    park in EPSG:5070, then measured by the macro's expression. It reads pyproj's Geod(ellps='WGS84') length of the
    same piece, taken back to lon/lat, to a micrometre, as decision 90's macro test holds the graph's edges."""
    to_projected = Transformer.from_crs(exporter.GEOGRAPHIC_CRS, exporter.PROJECTED_CRS, always_xy=True).transform
    to_geographic = Transformer.from_crs(exporter.PROJECTED_CRS, exporter.GEOGRAPHIC_CRS, always_xy=True).transform
    projected = [shapely_transform(to_projected, shapely.wkt.loads(wkt)) for wkt in (line_wkt, park_wkt)]
    con = spatial()

    (sql_m,) = con.execute(
        f"select {exporter._geodesic_metres('st_intersection(st_geomfromwkb(?), st_geomfromwkb(?))')}",
        [geometry.wkb for geometry in projected],
    ).fetchone()

    piece = shapely_transform(to_geographic, projected[0].intersection(projected[1]))
    assert sql_m == pytest.approx(Geod(ellps="WGS84").geometry_length(piece), abs=1e-6)
