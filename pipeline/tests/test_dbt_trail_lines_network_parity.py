"""The network's SQL answers what export_nearby_trails.py answers, on the same rows (#1793, stage 3).

The network half of trail_lines moved to SQL (pipeline/ELT.md's trail_lines
rule table, the TL rows for export_nearby_trails.py), and until stage 5
deletes the Python both are live. parity.py compares the two writers' files on
the fixture warehouse in CI; this holds the branches the fixtures never reach,
by running the Python over each dbt unit test's own rows, one test per model:

- int_trail_lines__blazes: lib/blaze.py, as each exporter composes it (TL03);
- int_trail_lines__network_sources: network_line_sources(),
  missing_declared_fields(), name_constant_conflicts() and dlt's own
  normalize_identifier() (TL01, TL08, TL09);
- int_trail_lines__network_judged: keep_reason(), declared_name(),
  load_boundary() and lib/feature_id.py (TL04-TL07, TL10, TL11, TL13, TL05),
  where DELIBERATE_IDS holds the two id rows that differ on purpose and
  parity.py's NETWORK_ID_REASONS has to name the same two cases;
- int_trail_lines__network_counts: count_problems();
- int_trail_lines__network_deduplicated: deduplicate(), publication first;
- int_trail_lines__network_area_closures: apply_area_closures(), NYS Parks'
  closed areas split onto the lines (#964);
- int_trail_lines__network_navigation: simplify_records() at 1 m (TL15);
- int_trail_lines__network_published: _rounded_geometry() (TL23);
- the overview's three models: _through_routes(), _above_the_seam_floor(),
  both passes' _simplified_part_by_part() and write_overview() itself (TL12,
  TL20, TL21);
- the network's dbt_project.yml vars are the Python's constants.

dbt runs the other half: each unit test holds the SQL to those expectations.
"""

import contextlib
import io
import json
from pathlib import Path

import duckdb
import numpy as np
import pytest
import shapely
import yaml
from dlt.common.normalizers.naming.sql_ci_v1 import NamingConvention
from pyproj import Geod

import export_nearby_trails
import export_trails
import parity
from lib import blaze
from lib.batch_geometry import from_wkt_all, reproject
from lib.completeness import count_problems
from lib.duplicates import DUPLICATE_MIN_SHARE, DUPLICATE_TOLERANCE_M
from lib.feature_id import resolve_feature_id
from tests.conftest import spatial_connection
from tests.test_dbt_trail_network_parity import _geodesic_length_sql

DBT = Path(__file__).parent.parent / "dbt"
NETWORK_YML = DBT / "models" / "intermediate" / "trail_lines" / "_trail_lines__network.yml"


def _document() -> dict:
    return yaml.safe_load(NETWORK_YML.read_text())


def _unit_test(name: str) -> dict:
    return next(test for test in _document()["unit_tests"] if test["name"] == name)


def _given(test: dict, model: str) -> list[dict]:
    return next(given["rows"] for given in test["given"] if given["input"] == f"ref('{model}')")


def _expected(test: dict) -> dict[str, dict]:
    return {row["trail_segment_key"]: row for row in test["expect"]["rows"]}


def _model(name: str) -> dict:
    return next(model for model in _document()["models"] if model["name"] == name)


# --- int_trail_lines__blazes (TL03) ---------------------------------------------

BLAZES = "int_trail_lines__blazes_answers_what_lib_blaze_answers"


def test_a_mapped_blaze_is_held_to_lib_blaze_palette_and_neutrals():
    column = next(c for c in _model("int_trail_lines__blazes")["columns"] if c["name"] == "blaze_color")
    (accepted,) = [
        test["accepted_values"] for test in column["data_tests"] if isinstance(test, dict) and "accepted_values" in test
    ]
    assert accepted["arguments"]["values"] == [*blaze.PALETTE, *blaze.NEUTRAL_MEMBERS]
    assert accepted["config"]["where"] == "blaze_disposition = 'mapped'"


def test_every_unit_test_row_has_an_expectation():
    test = _unit_test(BLAZES)
    keys = [
        row["trail_segment_key"]
        for model in ("stg_atc__centerline_segments", "stg_atc__side_trails", "int_trail_lines__network_unioned")
        for row in _given(test, model)
    ]
    assert sorted(keys) == sorted(_expected(test))


def test_the_at_rows_decode_and_map_as_export_trails_does(monkeypatch):
    """normalize_source_features(), with the live domain call and the reviewed
    file replaced by the unit test's own: the colour it attaches is the one the
    SQL expects, and the decode and disposition are those of the two lib/blaze.py
    calls it makes, in its order."""
    test = _unit_test(BLAZES)
    registry = {row["source_key"]: json.loads(row["entry"]) for row in _given(test, "stg_registry__sources")}
    (document,) = _given(test, "base_ourhike__blaze_mapping")
    mapping = json.loads(document["document_json"])["sources"]
    # side_trails' Blaze is esriFieldTypeString with codes '0' to '9' (tl-at,
    # 2026-10-02, from the live layer's domain), so the codes and the values
    # are both strings, as the unit test's rows hold them.
    domain = {row["code"]: row["label"] for row in _given(test, "int_trail_lines__coded_domains")}
    monkeypatch.setattr(export_trails, "get_field_coded_domain", lambda url, field: domain)
    monkeypatch.setattr(export_trails, "load_blaze_mapping", lambda: mapping)
    expected = _expected(test)

    rows = [(row, "centerline") for row in _given(test, "stg_atc__centerline_segments")]
    rows += [(row, "side_trails") for row in _given(test, "stg_atc__side_trails")]
    for row, key in rows:
        source = {"url": "https://example.test/at", **registry[key]}
        field = source.get("blaze_field")
        properties = {field: row.get("blaze")} if field else {}
        (normalized,) = export_trails.normalize_source_features(source, [{"properties": properties}])

        colour, decoded = blaze.normalize_blaze_color(
            properties.get(field) if field else None, domain if field else None, source.get("blaze_default")
        )
        disposition = None
        if mapping.get(key) is not None and decoded:
            colour, disposition = blaze.map_source_blaze(colour, mapping[key])
        assert normalized["_blaze_color"] == colour, row["trail_segment_key"]

        want = expected[row["trail_segment_key"]]
        assert (want["blaze_color"], want["blaze_decoded"], want["blaze_disposition"]) == (colour, decoded, disposition), row[
            "trail_segment_key"
        ]


def test_the_network_rows_resolve_as_resolve_blaze_does():
    """resolve_blaze() on each row's properties, read back under the registry's
    spelling of the field. Its 'default', for a source with no blaze field, is
    the SQL's null: the lead's column spec gives such a row no disposition."""
    test = _unit_test(BLAZES)
    (document,) = _given(test, "base_ourhike__blaze_mapping")
    mapping = json.loads(document["document_json"])["sources"]
    sources = {row["source_key"]: row for row in _given(test, "int_trail_lines__network_sources")}
    expected = _expected(test)

    for row in _given(test, "int_trail_lines__network_unioned"):
        declared = sources[row["source_key"]]
        source = {key: declared[key] for key in ("blaze_field", "blaze_default") if declared.get(key) is not None}
        landed = json.loads(row["properties"])
        properties = (
            {declared["blaze_field"]: landed[declared["blaze_column"]]}
            if "blaze_column" in declared and declared["blaze_column"] in landed
            else {}
        )
        colour, disposition = export_nearby_trails.resolve_blaze(source, properties, mapping.get(row["source_key"]))
        want = expected[row["trail_segment_key"]]
        assert want["blaze_decoded"] is True, row["trail_segment_key"]
        assert (want["blaze_color"], want["blaze_disposition"]) == (colour, None if disposition == "default" else disposition), (
            row["trail_segment_key"]
        )


@pytest.mark.parametrize("raw", ["Teal", "Pink", "Chartreuse"])
def test_a_reviewed_value_answers_the_same_whichever_export_asks(raw):
    """The two exports reach map_source_blaze() by different paths and must not
    disagree about one table: export_trails.py maps a decoded label, resolve_blaze()
    a raw value, and for a value that needs no decode the two are one call."""
    table = {"mapped": {"Teal": "Aqua"}, "deferred": {"Pink": {}}}
    source = {"blaze_field": "Blaze"}
    assert export_nearby_trails.resolve_blaze(source, {"Blaze": raw}, table) == blaze.map_source_blaze(raw, table)


# --- shared helpers for the network's unit tests ----------------------------------


def _rows(test: dict, model: str) -> list[dict]:
    """A given input's rows, as dicts: a `format: sql` input is run by DuckDB, as dbt runs it."""
    given = next(given for given in test["given"] if given["input"] == f"ref('{model}')")
    if given.get("format") != "sql":
        return given["rows"]
    relation = duckdb.sql(given["rows"])
    return [dict(zip(relation.columns, values)) for values in relation.fetchall()]


def _registry_source(row: dict) -> dict:
    """A sources.json entry, in the registry's spelling, from an int_trail_lines__network_sources row."""
    source = {"key": row["source_key"]}
    for field in ("name_field", "name_constant", "foot_field", "status_field", "boundary_source", "boundary_names"):
        if row.get(field) is not None:
            source[field] = row[field]
    if row.get("name_placeholders"):
        source["name_placeholders"] = row["name_placeholders"]
    if row.get("foot_allowed") is not None:
        source["foot_allowed"] = row["foot_allowed"]
    excluded = json.loads(row["excluded_when"]) if isinstance(row.get("excluded_when"), str) else row.get("excluded_when")
    if excluded:
        source["excluded_when"] = excluded
    return source


def _registry_properties(row: dict, landed: dict) -> dict:
    """A landed row's properties under the registry's spelling of each field it declares."""
    spelled = dict(zip(row["declared_columns"], row["declared_fields"]))
    spelled[row["name_column"]] = row["name_field"] or "Name"
    return {spelled.get(column, column): value for column, value in landed.items()}


def _coordinates(wkt: str) -> list:
    return shapely.get_coordinates(shapely.from_wkt(wkt)).tolist()


# --- the network's constants (dbt_project.yml's trail_lines network block) -------


def test_the_network_vars_are_the_python_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["trail_lines_network_navigation_tolerance_m"] == export_trails.DEFAULT_SIMPLIFY_TOLERANCE_M
    assert variables["trail_lines_network_coordinate_decimals"] == export_nearby_trails.NEARBY_COORDINATE_DECIMALS
    assert variables["trail_lines_network_duplicate_tolerance_m"] == DUPLICATE_TOLERANCE_M
    assert variables["trail_lines_network_duplicate_min_share"] == DUPLICATE_MIN_SHARE
    assert variables["trail_lines_network_inside_boundary_min_fraction"] == export_nearby_trails.INSIDE_BOUNDARY_MIN_FRACTION
    assert variables["trail_lines_network_overview_simplify_tolerance_m"] == export_trails.OVERVIEW_SIMPLIFY_TOLERANCE_M
    assert variables["trail_lines_network_chain_tolerance_m"] == export_nearby_trails.CHAIN_TOLERANCE_M
    assert variables["trail_lines_network_named_trail_threshold_miles"] == export_nearby_trails.NAMED_TRAIL_THRESHOLD_MILES
    assert variables["trail_lines_network_overview_min_feature_m"] == export_nearby_trails.OVERVIEW_MIN_FEATURE_M
    assert variables["trail_lines_network_overview_seam_tolerance_m"] == export_nearby_trails.OVERVIEW_SEAM_TOLERANCE_M
    assert variables["trail_lines_network_overview_seam_decimals"] == export_nearby_trails.OVERVIEW_SEAM_DECIMALS


def test_the_mile_the_sql_divides_by_is_the_pythons():
    assert export_nearby_trails.METERS_PER_MILE == 1609.344
    for name in ("int_trail_lines__network_overview_routes.sql",):
        assert "/ 1609.344" in (NETWORK_YML.parent / name).read_text(), name
    assert "/ 1609.344" in (DBT / "models" / "publish" / "pub_nearby_trails.sql").read_text()


# --- int_trail_lines__network_sources (TL01, TL08, TL09) --------------------------

SOURCES = "int_trail_lines__network_sources_answers_what_the_registry_checks_answer"


def test_the_registry_checks_answer_what_the_python_answers():
    """network_line_sources() picks the same entries; missing_declared_fields(),
    over each layer's landed rows read back in the registry's spelling, names
    the same fields; name_constant_conflicts() the same entries; and each
    column is dlt's own name for its field."""
    test = _unit_test(SOURCES)
    registry_rows = _rows(test, "stg_registry__sources")
    entries = [{**json.loads(row["entry"]), **({"kind": row["kind"]} if row["kind"] else {})} for row in registry_rows]
    expected = {row["source_key"]: row for row in test["expect"]["rows"]}
    sources = export_nearby_trails.network_line_sources({"sources": entries})
    assert [source["key"] for source in sources] == list(expected)

    naming = NamingConvention()
    landed: dict[str, list[dict]] = {}
    for row in _rows(test, "int_trail_lines__network_unioned"):
        landed.setdefault(row["source_key"], []).append(json.loads(row["properties"]))
    for source in sources:
        want = expected[source["key"]]
        declared = [source.get(k) for k in ("name_field", "foot_field", "blaze_field", "status_field")]
        declared += list(source.get("excluded_when") or {})
        features = [
            {
                "properties": {
                    field: props[naming.normalize_identifier(field)]
                    for field in declared
                    if field and naming.normalize_identifier(field) in props
                }
            }
            for props in landed.get(source["key"], [])
        ]
        missing = export_nearby_trails.missing_declared_fields(source, features) if features else []
        assert json.loads(want["missing_declared_fields"]) == missing, source["key"]
        assert want["name_column"] == naming.normalize_identifier(source.get("name_field", "Name")), source["key"]
        for field, column in (("foot_field", "foot_column"), ("blaze_field", "blaze_column"), ("status_field", "status_column")):
            assert want[column] == (naming.normalize_identifier(source[field]) if source.get(field) else None), (
                source["key"],
                field,
            )
    assert [key for key, row in expected.items() if row["declares_name_twice"]] == export_nearby_trails.name_constant_conflicts(
        sources
    )


def test_a_source_both_junior_and_senior_is_flagged_where_the_python_would_chain_it():
    """deduplicate() applies pairs one after another, so a source junior in one
    pair and senior in another would be answered pair by pair; the SQL compares
    every pair at once, so it refuses such a chain instead (the model's test on
    `chains_duplicates`). The flag is exactly the chains the registry rows declare."""
    test = _unit_test(SOURCES)
    entries = [json.loads(row["entry"]) for row in _rows(test, "stg_registry__sources")]
    seniors = {entry["duplicate_of"] for entry in entries if entry.get("duplicate_of")}
    chained = {entry["key"] for entry in entries if entry.get("duplicate_of") and entry["key"] in seniors}
    assert {row["source_key"] for row in test["expect"]["rows"] if row["chains_duplicates"]} == chained == {"junior_and_senior"}


# --- int_trail_lines__network_judged (TL04-TL07, TL10, TL11, TL13, placeholders) ---

JUDGED = "int_trail_lines__network_judged_answers_what_keep_reason_answers"

#: Unit-test rows whose published id the SQL and the Python build differently
#: on purpose, by the parity reason each is (parity.py's NETWORK_ID_REASONS).
#: Emptying this, or that, turns the tests below red.
DELIBERATE_IDS = {
    "sql::a_globalid_in_capitals_is_still_the_id": "globalid_in_any_case",
    "sql::a_feature_id_the_extract_does_not_land": "feature_id_not_landed",
}

#: What the Python's feature carried that the warehouse does not: the
#: GlobalID's own spelling, and the GeoJSON `id` the extract does not land.
PYTHON_FEATURES = {
    "sql::a_globalid_in_capitals_is_still_the_id": {"globalid": "GLOBALID"},
    "sql::a_feature_id_the_extract_does_not_land": {"feature_id": "row-7"},
}


def _boundary_answers(test: dict, sources: dict, tmp_path, monkeypatch) -> dict[str, tuple]:
    """load_boundary() for each source, against the unit test's polygons written as the layer it reads."""
    polygons = [
        {
            "type": "Feature",
            "properties": {"signname": row["signname"]},
            "geometry": shapely.from_wkt(row["geom"]).__geo_interface__,
        }
        for row in _rows(test, "base_nycparks__nyc_park_polygons")
    ]
    (tmp_path / "nyc_park_polygons.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": polygons}))
    monkeypatch.setattr(export_nearby_trails, "RAW_DIR", tmp_path)
    answers = {}
    for key, source in sources.items():
        try:
            answers[key] = (export_nearby_trails.load_boundary(source), False)
        except (SystemExit, FileNotFoundError):
            answers[key] = (None, True)
    return answers


def test_keep_reason_declared_name_and_the_id_chain_answer_what_the_unit_test_expects(tmp_path, monkeypatch):
    test = _unit_test(JUDGED)
    source_rows = {row["source_key"]: row for row in _rows(test, "int_trail_lines__network_sources")}
    sources = {key: _registry_source(row) for key, row in source_rows.items()}
    owned: dict[str, str] = {}
    for row in sorted(_rows(test, "stg_registry__sources"), key=lambda row: row["file_row"]):
        for name in json.loads(row["entry"]).get("owns_route_names", []):
            owned[name] = row["source_key"]
    boundaries = _boundary_answers(test, sources, tmp_path, monkeypatch)
    expected = _expected(test)
    assert len(expected) == len(_rows(test, "int_trail_lines__network_unioned"))

    for row in _rows(test, "int_trail_lines__network_unioned"):
        key, source = row["trail_segment_key"], sources[row["source_key"]]
        landed = json.loads(row["properties"])
        properties = _registry_properties(source_rows[row["source_key"]], landed)
        hints = PYTHON_FEATURES.get(key, {})
        if "globalid" in properties:
            properties[hints.get("globalid", "GlobalID")] = properties.pop("globalid")
        feature_id = hints.get("feature_id", landed.get("objectid"))
        geometry = shapely.from_wkt(row["geom"]) if row.get("geom") else None
        boundary, refused = boundaries[row["source_key"]]
        want = expected[key]

        assert want["boundary_missing"] is refused, key
        if refused:
            assert want["dropped_because"] == "outside the boundary its registry entry names", key
            continue
        reason = export_nearby_trails.keep_reason(source, properties, geometry, owned, boundary)
        if reason is None and export_trails.geometry_to_wkt(geometry.__geo_interface__) is None:
            reason = "unsupported geometry"
        assert want["dropped_because"] == reason, key
        if reason is not None:
            continue

        assert want["name"] == export_nearby_trails.declared_name(source, properties), key
        status_field = source.get("status_field")
        status = (
            export_nearby_trails.SHIPPED_STATUSES.get(properties.get(status_field), export_nearby_trails.DEFAULT_STATUS)
            if status_field
            else export_nearby_trails.DEFAULT_STATUS
        )
        assert want["trail_status"] == status, key
        assert want["trail_status_basis"] == ("stated" if status_field else "default_without_status_column"), key
        assert want["closure_kind"] == ("long_term" if status == "closed" else None), key

        with contextlib.redirect_stdout(io.StringIO()):
            python_id = f"{source['key']}:{resolve_feature_id(source['key'], {'id': feature_id} if feature_id is not None else {}, properties, row.get('source_row') or 0)}"
        if key in DELIBERATE_IDS:
            assert want["trail_line_id"] != python_id, f"{key} is no longer a deliberate difference"
        else:
            assert want["trail_line_id"] == python_id, key


def test_every_deliberate_id_difference_is_a_reason_parity_names():
    assert set(DELIBERATE_IDS.values()) == set(parity.NETWORK_ID_REASONS)


# --- int_trail_lines__network_counts (fail_if_incomplete) --------------------------

COUNTS = "int_trail_lines__network_counts_find_what_fail_if_incomplete_finds"


def test_the_sources_keeping_nothing_are_the_ones_count_problems_names():
    test = _unit_test(COUNTS)
    kept = {row["source_key"]: row["rows_kept"] for row in test["expect"]["rows"]}
    problems = count_problems(kept)
    assert sorted(problem.split(":")[0] for problem in problems) == sorted(key for key, n in kept.items() if n < 1)
    judged = _rows(test, "int_trail_lines__network_judged")
    for key in kept:
        rows = [row for row in judged if row["source_key"] == key]
        assert kept[key] == sum(row["dropped_because"] is None for row in rows), key


# --- int_trail_lines__network_deduplicated (TL18) ----------------------------------

DEDUPLICATED = "int_trail_lines__network_deduplicated_answers_what_deduplicate_answers"


def _deduplicated_by_python(test: dict, *, publication_first: bool) -> list[dict]:
    rows = sorted(_rows(test, "int_trail_lines__network_judged"), key=lambda row: (row["file_row"], row["trail_segment_key"]))
    blazes = {row["trail_segment_key"]: row["blaze_color"] for row in _rows(test, "int_trail_lines__blazes")}
    shipping = [row for row in rows if row["may_publish"] or not publication_first]
    sources = list(
        {
            row["source_key"]: {
                "key": row["source_key"],
                **({"duplicate_of": row["duplicate_of"]} if row["duplicate_of"] else {}),
            }
            for row in shipping
        }.values()
    )
    records = [
        {
            "id": row["trail_line_id"],
            "source": row["source_key"],
            "name": row["name"],
            "blaze_color": blazes[row["trail_segment_key"]],
            "trail_status": row["trail_status"],
            "wkt": row["geom_wkt"],
        }
        for row in shipping
        if row["dropped_because"] is None
    ]
    kept, _ = export_nearby_trails.deduplicate(records, export_nearby_trails.declared_duplicate_pairs(sources))
    return kept


def test_deduplicate_keeps_and_merges_what_the_unit_test_expects():
    """Publication first, as pipeline/ELT.md has it ("Publication filters run
    before dedup"): a row whose source may not publish is gone before any line
    is compared, so it can never swallow a line that ships."""
    test = _unit_test(DEDUPLICATED)
    kept = {record["id"]: record for record in _deduplicated_by_python(test, publication_first=True)}
    expected = {row["trail_line_id"]: row for row in test["expect"]["rows"]}
    assert set(expected) == set(kept)
    for line_id, want in expected.items():
        record = kept[line_id]
        assert (want["name"], want["trail_status"], want["blaze_color"], want["duplicate_of"]) == (
            record["name"],
            record["trail_status"],
            record["blaze_color"],
            record.get("duplicate_of"),
        ), line_id
        assert _coordinates(want["geom_wkt"]) == _coordinates(record["wkt"]), line_id


def test_without_publication_first_a_held_back_senior_would_swallow_a_line_that_ships():
    """The difference publication-first makes, held so it stays deliberate:
    today's export compares every exported source, held back or not, and
    publish.py then holds the whole file back."""
    test = _unit_test(DEDUPLICATED)
    unfiltered = {record["id"] for record in _deduplicated_by_python(test, publication_first=False)}
    junior = "junior_of_held:test_export_nearby_trails::test_a_junior_whose_senior_is_not_shipping_is_skipped[junior]"
    assert junior not in unfiltered
    assert junior in {row["trail_line_id"] for row in test["expect"]["rows"]}


# --- int_trail_lines__network_area_closures (#964) ----------------------------------

AREA_CLOSURES = "int_trail_lines__network_area_closures_answers_what_apply_area_closures_answers"
NO_CLOSED_AREA = "int_trail_lines__network_area_closures_leaves_every_trail_as_it_was_with_no_closed_area"


def _closed_areas_by_python(test: dict) -> list[dict]:
    """apply_area_closures() over a unit test's own lines and areas, the areas in
    the layer's order (`source_row`), each read as load_closure_areas() reads one."""
    records = [
        {
            "id": row["trail_line_id"],
            "wkt": row["geom_wkt"],
            "trail_status": row["trail_status"],
            "closure_kind": row["closure_kind"],
        }
        for row in _rows(test, "int_trail_lines__network_deduplicated")
    ]
    areas = [
        {
            "geometry": shapely.geometry.shape(json.loads(row["geom_geojson"])),
            "reason": (row["closure_reason"] or "").strip() or None,
            "source": "oprhp_trail_closures",
        }
        for row in sorted(_rows(test, "int_closures__oprhp_areas"), key=lambda row: row["source_row"])
    ]
    split, _ = export_nearby_trails.apply_area_closures(records, areas)
    return split


@pytest.mark.parametrize("name", [AREA_CLOSURES, NO_CLOSED_AREA])
def test_the_closed_areas_split_the_lines_as_apply_area_closures_splits_them(name):
    """Every section the Python ships, with its id, status, kind, reason and
    the closure layer's key, and its vertices to the bit; and nothing else."""
    test = _unit_test(name)
    split = {record["id"]: record for record in _closed_areas_by_python(test)}
    expected = {row["trail_line_id"]: row for row in test["expect"]["rows"]}
    assert set(expected) == set(split)
    for line_id, want in expected.items():
        record = split[line_id]
        assert (want["trail_status"], want["closure_kind"], want["closure_reason"], want["closure_source"]) == (
            record["trail_status"],
            record.get("closure_kind"),
            record.get("closure_reason"),
            record.get("closure_source"),
        ), line_id
        assert _coordinates(want["geom_wkt"]) == _coordinates(record["wkt"]), line_id
        assert (want["trail_status_basis"] == "closed_area") is (record.get("closure_kind") == "area"), line_id


def test_the_unit_tests_tie_would_answer_otherwise_if_broken_by_key():
    """The two nested areas tie on the line inside both, and the one first in
    the layer gives the reason. Its key sorts after the other's, so a model
    breaking the tie by key instead of by `source_row` fails the unit test."""
    test = _unit_test(AREA_CLOSURES)
    areas = {row["closure_reason"]: row for row in _rows(test, "int_closures__oprhp_areas")}
    outer, inner = areas["Closed: the outer area"], areas["Closed: the inner area"]
    assert outer["source_row"] < inner["source_row"]
    assert outer["closure_key"] > inner["closure_key"]
    tied = next(row for row in test["expect"]["rows"] if "a tie goes to the area first" in row["trail_segment_key"])
    assert tied["closure_reason"] == "Closed: the outer area"


# --- int_trail_lines__network_navigation (TL15) ------------------------------------

NAVIGATION = "int_trail_lines__network_navigation_answers_what_simplify_records_answers"


def test_the_1_m_pass_is_simplify_records_vertex_for_vertex():
    test = _unit_test(NAVIGATION)
    expected = _expected(test)
    for row in _rows(test, "int_trail_lines__network_area_closures"):
        (record,) = export_trails.simplify_records([{"id": row["trail_line_id"], "wkt": row["geom_wkt"]}])
        geoms = np.array([shapely.from_wkt(row["geom_wkt"])], dtype=object)
        reduced = reproject(
            shapely.simplify(
                reproject(geoms, export_trails._TO_METRIC), export_trails.DEFAULT_SIMPLIFY_TOLERANCE_M, preserve_topology=False
            ),
            export_trails._TO_GEOGRAPHIC,
        )
        want = expected[row["trail_segment_key"]]
        assert _coordinates(want["geom_wkt"]) == _coordinates(record["wkt"]), row["trail_segment_key"]
        assert want["kept_full_resolution"] is (not bool(export_trails._drawable_all(reduced)[0])), row["trail_segment_key"]


# --- int_trail_lines__network_published (TL23) ---------------------------------------

PUBLISHED = "int_trail_lines__network_published_cuts_what_rounded_geometry_cuts"


def test_the_six_decimal_cut_is_rounded_geometry_and_the_order_is_registry_then_id():
    test = _unit_test(PUBLISHED)
    rows = _rows(test, "int_trail_lines__network_navigation")
    order = {
        row["trail_line_id"]: n for n, row in enumerate(sorted(rows, key=lambda row: (row["file_row"], row["trail_line_id"])))
    }
    expected = {row["trail_line_id"]: row for row in test["expect"]["rows"]}
    for row in rows:
        want = expected[row["trail_line_id"]]
        cut = export_nearby_trails._rounded_geometry(shapely.from_wkt(row["geom_wkt"]))
        assert want["geom_geojson"] == json.dumps(cut, separators=(",", ":")), row["trail_line_id"]
        assert want["feature_order"] == order[row["trail_line_id"]], row["trail_line_id"]


GEODESIC = "int_trail_lines__network_published_measures_both_lengths_on_the_wgs84_ellipsoid"


def test_length_miles_and_published_length_m_are_both_pyprojs_wgs84_geodesic():
    """Decision 97: on that unit test's rows, records_to_geojson()'s `length_miles` is the expected
    published_length_m in miles at 2 decimals, as pub_nearby_trails rounds it, and the expected metres are pyproj's
    Geod(ellps='WGS84') length, records_to_geojson()'s and macros/geodesic_length_m.sql's, each to a micrometre.
    dbt holds the model to the expected metres only to 0.05 m (a 2.0.6 unit test compares a double at one decimal);
    the macro here is applied as the model applies it, to the lon/lat line projected to EPSG:5070."""
    test = _unit_test(GEODESIC)
    rows = _rows(test, "int_trail_lines__network_navigation")
    expected = {row["trail_line_id"]: row for row in test["expect"]["rows"]}
    records = [
        {
            "id": row["trail_line_id"],
            "source": row["source_key"],
            "name": row["name"],
            "blaze_color": row["blaze_color"],
            "wkt": row["geom_wkt"],
        }
        for row in rows
    ]
    features = export_nearby_trails.records_to_geojson(records)["features"]
    for row, feature in zip(rows, features, strict=True):
        want = expected[row["trail_line_id"]]
        assert want["published_length_m"] == want["length_m"], "the line is not simplified, so the two lengths agree"
        miles = round(want["published_length_m"] / export_nearby_trails.METERS_PER_MILE, 2)
        assert feature["properties"]["length_miles"] == miles, row["trail_segment_key"]

    geod = Geod(ellps="WGS84")
    con = spatial_connection()
    measured = _geodesic_length_sql("st_transform(st_geomfromtext(?), 'EPSG:4326', 'EPSG:5070', always_xy := true)")
    python_miles = export_nearby_trails._geodesic_miles_all(from_wkt_all([row["geom_wkt"] for row in rows]))
    for row, miles in zip(rows, python_miles, strict=True):
        pyproj_m = geod.geometry_length(shapely.from_wkt(row["geom_wkt"]))
        (sql_m,) = con.execute(f"select {measured}", [row["geom_wkt"]]).fetchone()
        assert expected[row["trail_line_id"]]["published_length_m"] == pytest.approx(pyproj_m, abs=1e-6)
        assert sql_m == pytest.approx(pyproj_m, abs=1e-6), row["trail_segment_key"]
        assert miles * export_nearby_trails.METERS_PER_MILE == pytest.approx(pyproj_m, abs=1e-6), row["trail_segment_key"]


# --- the overview sketch (TL12, TL20, TL21) ------------------------------------------

ROUTES = "int_trail_lines__network_overview_routes_answers_what_through_routes_answers"
SEAM = "int_trail_lines__network_overview_seam_answers_what_the_floor_and_seam_answer"
FEATURES = "int_trail_lines__network_overview_features_answer_what_write_overview_writes"


def test_through_routes_are_the_ones_through_routes_finds(monkeypatch):
    test = _unit_test(ROUTES)
    aliases = {
        (row["source_key"], row["published_spelling"]): row["trail_name"]
        for row in _rows(test, "int_trail_lines__network_name_aliases")
    }
    monkeypatch.setattr(export_nearby_trails, "_alias_index", lambda: aliases)
    rows = _rows(test, "int_trail_lines__network_navigation")
    records = [
        {
            "id": row["trail_line_id"],
            "source": row["source_key"],
            "name": row["name"],
            "blaze_color": row["blaze_color"],
            "trail_status": row["trail_status"],
            "wkt": row["geom_wkt"],
        }
        for row in rows
    ]
    coarse = export_nearby_trails._simplified_part_by_part(records, export_trails.OVERVIEW_SIMPLIFY_TOLERANCE_M)
    qualifying = export_nearby_trails._through_routes(coarse)
    expected = {row["trail_line_id"]: row for row in test["expect"]["rows"]}
    assert set(qualifying.values()) == {"Long Path", "Continental Divide Trail"}, "the cases no longer reach both branches"
    for index, record in enumerate(coarse):
        want = expected[record["id"]]
        identity = export_nearby_trails._trail_identity(record, aliases)
        assert want["trail_identity"] == (identity[1] if identity else None), record["id"]
        assert want["through_route"] == qualifying.get(index), record["id"]
        assert _coordinates(want["coarse_wkt"]) == _coordinates(record["wkt"]), record["id"]


def test_the_floor_and_the_seam_keep_and_cut_what_the_python_keeps_and_cuts():
    test = _unit_test(SEAM)
    records = []
    for row in _rows(test, "int_trail_lines__network_overview_routes"):
        record = {
            "id": row["trail_line_id"],
            "source": row["source_key"],
            "name": row["through_route"],
            "blaze_color": row["blaze_color"],
            "trail_status": row["trail_status"],
            "wkt": row["coarse_wkt"],
        }
        record[export_nearby_trails._THROUGH_ROUTE_KEY] = row["through_route"]
        records.append(record)
    kept = export_nearby_trails._above_the_seam_floor(records)
    seam = export_nearby_trails._simplified_part_by_part(kept, export_nearby_trails.OVERVIEW_SEAM_TOLERANCE_M)
    expected = {row["trail_line_id"]: row for row in test["expect"]["rows"]}
    assert len(kept) < len(records), "no row is under the floor, so the floor is untested"
    assert set(expected) == {record["id"] for record in seam}
    for record in seam:
        assert _coordinates(expected[record["id"]]["seam_wkt"]) == _coordinates(record["wkt"]), record["id"]
        assert expected[record["id"]]["through_route"] == record[export_nearby_trails._THROUGH_ROUTE_KEY], record["id"]


def test_the_sketchs_features_are_the_ones_write_overview_writes(tmp_path, monkeypatch):
    """write_overview() itself, run over lines that clear the floor and pass the
    seam's pass unchanged at three decimals, records in line-id order, so its
    parts come in the SQL's order."""
    test = _unit_test(FEATURES)
    rows = sorted(_rows(test, "int_trail_lines__network_overview_seam"), key=lambda row: row["trail_line_id"])
    records = [
        {
            "id": row["trail_line_id"],
            "source": row["source_key"],
            "name": row["through_route"],
            "blaze_color": row["blaze_color"],
            "trail_status": row["trail_status"],
            "wkt": row["seam_wkt"],
        }
        for row in rows
    ]
    monkeypatch.setattr(export_nearby_trails, "OUT_DIR", tmp_path)
    export_nearby_trails.write_overview(records)
    features = json.loads((tmp_path / export_nearby_trails.OVERVIEW_ARTIFACT_NAME).read_text())["features"]
    expected = sorted(test["expect"]["rows"], key=lambda row: row["feature_order"])
    assert [json.loads(row["properties_json"]) for row in expected] == [feature["properties"] for feature in features]
    assert [json.loads(row["coordinates_json"]) for row in expected] == [
        feature["geometry"]["coordinates"] for feature in features
    ]


# --- parity.py's network families --------------------------------------------------


def _line(feature_id: str, name: str, coordinates: list) -> dict:
    return {
        "type": "Feature",
        "properties": {"id": feature_id, "source": "s", "name": name},
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


def test_parity_explains_an_id_only_difference_and_nothing_else():
    family = parity.FAMILIES["nearby_trails"]
    old = {
        "type": "FeatureCollection",
        "features": [_line("s:1", "A", [[0.0, 0.0], [1.0, 1.0]]), _line("s:2", "B", [[2.0, 2.0], [3.0, 3.0]])],
    }
    new = {
        "type": "FeatureCollection",
        "features": [_line("s:{G-1}", "A", [[0.0, 0.0], [1.0, 1.0]]), _line("s:2", "B renamed", [[2.0, 2.0], [3.0, 3.0]])],
    }
    found = parity.differences(old, new, family)
    reasons = family.explained(old, new)
    assert {what for what, _, _ in found} == {"properties.id s:1", "properties.id s:{G-1}", "properties.id s:2"}
    assert set(reasons) == {"properties.id s:1", "properties.id s:{G-1}"}
    assert reasons["properties.id s:1"] == parity.NETWORK_ID_REASONS["globalid_in_any_case"]


def test_parity_explains_copies_of_one_line_the_dbt_writer_published_once_and_not_a_line_it_lost():
    family = parity.FAMILIES["nearby_trails"]
    a, b = [[0.0, 0.0], [1.0, 1.0]], [[2.0, 2.0], [3.0, 3.0]]
    old = {"features": [_line("s:1", "A", a), _line("s:2", "A", a), _line("s:3", "A", a), _line("s:4", "B", b)]}
    new = {"features": [_line("s:{R-1}", "A", a)]}
    reasons = family.explained(old, new)
    assert {f"properties.id s:{n}" for n in (1, 2, 3)} | {"properties.id s:{R-1}"} == set(reasons)
    assert set(reasons.values()) == {parity.NETWORK_COPY_REASON}
    # Line B is gone from the new file, and no copy of it is left there, so nothing explains its absence.
    assert "properties.id s:4" not in reasons


def test_parity_never_explains_two_positional_ids_that_name_different_lines():
    family = parity.FAMILIES["nearby_trails"]
    a, b = [[0.0, 0.0], [1.0, 1.0]], [[2.0, 2.0], [3.0, 3.0]]
    old = {"features": [_line("s:generated-0", "A", a), _line("s:generated-1", "A", b)]}
    new = {"features": [_line("s:generated-0", "A", b), _line("s:generated-1", "A", a)]}
    assert parity.differences(old, new, family)
    assert family.explained(old, new) == {}


def test_parity_compares_a_sketch_features_parts_as_a_set():
    family = parity.FAMILIES["network_overview"]

    def sketch(*parts):
        return {
            "features": [
                {
                    "type": "Feature",
                    "properties": {"source": "s", "blaze_color": "Red", "trail_status": "open"},
                    "geometry": {"type": "MultiLineString", "coordinates": list(parts)},
                }
            ]
        }

    one, two = [[0.0, 0.0], [1.0, 1.0]], [[2.0, 2.0], [3.0, 3.0]]
    assert parity.differences(sketch(one, two), sketch(two, one), family) == []
    assert parity.differences(sketch(one, two), sketch(one), family) != []


def test_parity_explains_a_club_line_as_decision_64s_new_data_and_nothing_else():
    """Decision 64 draws the clubs' own lines in nearby_trails.geojson, each marked `line_kind` 'club'. Parity explains
    a club line the new file adds, and never a network line it adds."""
    family = parity.FAMILIES["nearby_trails"]
    network = _line("s:1", "A", [[0.0, 0.0], [1.0, 1.0]])
    club = _line("fltc_flt_main:k", "Finger Lakes Trail", [[2.0, 2.0], [3.0, 3.0]])
    club["properties"]["line_kind"] = "club"
    added_network = _line("s:2", "B", [[4.0, 4.0], [5.0, 5.0]])
    old = {"features": [network]}
    new = {"features": [network, club, added_network]}

    assert {what for what, _, _ in parity.differences(old, new, family)} == {
        "properties.id fltc_flt_main:k",
        "properties.id s:2",
    }
    assert family.explained(old, new) == {"properties.id fltc_flt_main:k": parity.CLUB_LINE_REASON}
    assert parity.CLUB_LINE_REASON.startswith(parity.NEW_DATA_REASON)


def test_parity_explains_a_club_group_after_the_network_in_the_sketch_and_not_before_it():
    family = parity.FAMILIES["network_overview"]

    def group(source: str, **properties) -> dict:
        return {
            "type": "Feature",
            "properties": {"source": source, "blaze_color": "Unknown", **properties},
            "geometry": {"type": "MultiLineString", "coordinates": [[[0.0, 0.0], [1.0, 1.0]]]},
        }

    network = group("dec_hiking_trails", trail_status="open")
    club = group("fltc_flt_main", line_kind="club")
    old = {"features": [network]}

    after = {"features": [network, club]}
    reasons = family.explained(old, after)
    assert set(reasons) == {f"{family.key} {parity._overview_key(club)}", "order"}
    assert {what for what, _, _ in parity.differences(old, after, family)} <= set(reasons)

    # A club group drawn ahead of the network moves the network's own features: not explained.
    before = {"features": [club, network]}
    assert "order" not in family.explained(old, before)
