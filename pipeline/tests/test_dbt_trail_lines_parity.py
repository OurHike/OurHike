"""The trail_lines family's SQL answers what today's Python answers, on the same rows (#1793, stage 3).

The A.T. mile axis moved to SQL (pipeline/ELT.md's ledger rows EL01-EL04, built
by the trail_lines family because every A.T. mile comes off it). Until stage 5
deletes the Python, export_elevation.calibrated_trail_axis still builds the
axis that export_poi.py, export_spurs.py and export_trails.py publish miles
from, so the two copies are held together here:

- the mile_axis_* vars the models read are export_elevation.py's constants;
- each mile-axis unit test's given rows are the previous test's expected
  rows, so the four tests are one run of the axis from segments to gate;
- export_elevation.py's own functions, run over those rows, give every
  expected row, to the bit wherever the unit test compares to the bit.

dbt runs the other half: each unit test holds the SQL to its expected rows.
A dbt 2.0.6 unit test compares a DOUBLE column only to one decimal place
(measured 2026-10-02, int_trail_lines__mile_axis_calibration's header), so
the numbers that must agree exactly travel as WKT and JSON text there, and
this file is what holds the doubles (markers' along_m, the holdout's figures)
to the Python exactly.

The coded-value domains export_trails.py and export_spurs.py fetch live are a
var here (trail_lines_coded_domains, read by int_trail_lines__coded_domains),
and this file holds that frozen copy to the domains those exporters' own tests
decode with, so a typo in the var fails a test rather than a hiker's blaze.

The rest of the A.T.'s models have their unit tests in
_trail_lines__unit_tests.yml, one row or one test per pytest case of the files
pipeline/ELT.md's ledger lists for tl-at's rows. Below, today's functions run
over each test's given rows (resolve_feature_id, load_line_sources,
simplify_records, merge_chain_records, vertex_miles, write_overview,
build_spur_records with attach_junction_miles, _rounded_geometry,
build_stretches, canonical_clubs, assemble) and must give every expected row,
except where DELIBERATE names the row and the reason; ELSEWHERE places every
ledger-listed case no unit test names.
"""

import functools
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest
import shapely.geometry
import yaml
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import transform as shapely_transform
from shapely.strtree import STRtree

import export_club_sections
import export_elevation
import export_nearby_trails
import export_spurs
import export_trails
from lib import club_sections as lib_club_sections
from lib import corridor
from lib import spurs as lib_spurs
from lib.feature_id import resolve_feature_id
from tests.conftest import spatial_connection
from tests.test_export_spurs import TYPE_DOMAIN as EXPORT_SPURS_TYPE_DOMAIN
from tests.test_export_trails import BLAZE_DOMAIN_RESPONSE
from tests.test_lib_blaze import SIDE_TRAILS_BLAZE_DOMAIN
from tests.test_lib_spurs import TYPE_DOMAIN as LIB_SPURS_TYPE_DOMAIN

DBT = Path(__file__).parent.parent / "dbt"
INTERMEDIATE = DBT / "models" / "intermediate" / "trail_lines" / "_trail_lines__intermediate.yml"


def _unit_test(name: str) -> dict:
    return next(test for test in yaml.safe_load(INTERMEDIATE.read_text())["unit_tests"] if test["name"] == name)


def _given(test: dict, model: str) -> list[dict]:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")["rows"]


PIECES = _unit_test("int_trail_lines__mile_axis_pieces_merges_and_orders_like_export_elevation")
MARKERS = _unit_test("int_trail_lines__mile_axis_markers_snaps_like_export_elevation")
CALIBRATION = _unit_test("int_trail_lines__mile_axis_calibration_orients_and_scales_like_export_elevation")
HOLDOUT = _unit_test("int_trail_lines__mile_axis_holdout_refuses_a_median_over_the_gate")
HOLDOUT_P95 = _unit_test("int_trail_lines__mile_axis_holdout_refuses_a_p95_over_the_gate")
HOLDOUT_MAX = _unit_test("int_trail_lines__mile_axis_holdout_refuses_a_maximum_over_the_gate")


@pytest.fixture(scope="module")
def con():
    connection = spatial_connection()
    yield connection
    connection.close()


def test_the_mile_axis_vars_are_export_elevations_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert (variables["mile_axis_springer_lon"], variables["mile_axis_springer_lat"]) == export_elevation.SPRINGER_LONLAT
    assert (variables["mile_axis_katahdin_lon"], variables["mile_axis_katahdin_lat"]) == export_elevation.KATAHDIN_LONLAT
    assert variables["mile_axis_marker_snap_max_m"] == export_elevation.MARKER_SNAP_MAX_M
    assert variables["mile_axis_metres_per_mile"] == export_elevation.METERS_PER_MILE
    assert variables["mile_axis_holdout_max_median_mi"] == export_elevation.MARKER_HOLDOUT_MAX_MEDIAN_MI
    assert variables["mile_axis_holdout_max_p95_mi"] == export_elevation.MARKER_HOLDOUT_MAX_P95_MI
    assert variables["mile_axis_holdout_max_mi"] == export_elevation.MARKER_HOLDOUT_MAX_MI


def test_the_at_line_vars_are_export_trails_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["trail_lines_corridor_buffer_miles"] == corridor.BUFFER_MILES
    assert variables["trail_lines_simplify_tolerance_m"] == export_trails.DEFAULT_SIMPLIFY_TOLERANCE_M
    assert variables["trail_lines_overview_tolerance_m"] == export_trails.OVERVIEW_SIMPLIFY_TOLERANCE_M
    assert variables["trail_lines_overview_decimals"] == export_trails.OVERVIEW_COORDINATE_DECIMALS
    assert variables["trail_lines_mile_decimals"] == export_trails.TRAIL_MILE_DECIMALS
    # Decision 8's six decimals for trails.geojson, the network file's own cut.
    assert variables["trail_lines_published_decimals"] == export_nearby_trails.NEARBY_COORDINATE_DECIMALS


def test_the_models_merge_only_the_sources_export_trails_merges():
    """int_trail_lines__at_chains, __at_overview and __at_side_trails name the centerline as the merged source."""
    assert export_trails.CHAIN_MERGED_SOURCES == ("centerline",)
    for model in ("int_trail_lines__at_chains", "int_trail_lines__at_overview", "int_trail_lines__at_side_trails"):
        text = (DBT / "models" / "intermediate" / "trail_lines" / f"{model}.sql").read_text()
        assert "source_key in ('centerline')" in text or "source_key not in ('centerline')" in text, model


def test_the_spur_vars_are_lib_spurs_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["trail_lines_spur_type_code"] == lib_spurs.SPUR_TYPE_CODE
    assert dict(map(tuple, variables["trail_lines_type_literal_aliases"])) == lib_spurs.TYPE_LITERAL_ALIASES
    assert variables["trail_lines_spur_junction_max_m"] == lib_spurs.JUNCTION_MAX_M
    assert variables["trail_lines_spur_on_trail_m"] == lib_spurs.ON_TRAIL_M
    assert variables["trail_lines_spur_destination_max_m"] == lib_spurs.DESTINATION_MAX_M
    assert variables["trail_lines_metres_per_degree"] == lib_spurs.METERS_PER_DEGREE
    assert variables["trail_lines_spur_destination_poi_types"] == list(export_spurs.DESTINATION_POI_TYPES)
    assert (export_spurs.SIDE_TRAILS_KEY, export_spurs.TYPE_FIELD) == ("side_trails", "Type")


def test_the_club_vars_are_lib_club_sections_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["trail_lines_club_milepost_snap_m"] == lib_club_sections.MILEPOST_SNAP_M
    assert variables["trail_lines_club_stretch_gap_mi"] == lib_club_sections.STRETCH_GAP_MILES
    assert variables["trail_lines_club_milepost_half_width_mi"] == lib_club_sections.MILEPOST_HALF_WIDTH
    assert variables["trail_lines_club_springer_mile"] == lib_club_sections.SPRINGER_MILE


def test_the_club_models_read_the_layers_and_fields_export_club_sections_reads():
    """The source keys the club models gate on, and the upstream fields their staged columns come from."""
    models = DBT / "models" / "intermediate" / "trail_lines"
    stretches = (models / "int_trail_lines__club_stretches.sql").read_text()
    names = (models / "int_trail_lines__club_names.sql").read_text()
    assert f"'{export_club_sections.CENTERLINE_KEY}'" in stretches
    assert f"'{export_club_sections.MILEPOSTS_KEY}'" in stretches
    assert f"'{export_club_sections.POLYGONS_KEY}'" in names
    staging = DBT / "models" / "staging" / "atc"
    assert (
        f"{lib_club_sections.POLYGON_ACRONYM_FIELD.lower()} as club_acronym"
        in (staging / "stg_atc__club_sections.sql").read_text()
    )
    assert (
        f"{export_club_sections.MEASURE_FIELD.lower()} as measure_mi" in (staging / "stg_atc__half_mile_markers.sql").read_text()
    )
    assert lib_club_sections.CENTERLINE_ACRONYM_FIELD == "Acronym"
    assert "acronym as club_acronym" in (staging / "stg_atc__centerline_segments.sql").read_text()
    assert (lib_club_sections.POLYGON_NAME_FIELD, lib_club_sections.POLYGON_REGION_FIELD) == ("TRAIL_CLUB", "REGION")


def _coded_domain(source_key: str, field_name: str) -> dict[str, str]:
    """One field's rows of the trail_lines_coded_domains var, as {code: label}."""
    rows = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]["trail_lines_coded_domains"]
    return {code: label for source, field, code, label in rows if (source, field) == (source_key, field_name)}


def test_the_coded_domains_var_is_the_blaze_domain_export_trails_tests_decode_with():
    """side_trails' Blaze is test_lib_blaze.py's whole domain, its codes as the text the layer serves."""
    blaze = _coded_domain("side_trails", "Blaze")
    assert blaze == {str(code): label for code, label in SIDE_TRAILS_BLAZE_DOMAIN.items()}
    served = BLAZE_DOMAIN_RESPONSE["fields"][0]["domain"]["codedValues"]
    assert {value["code"]: value["name"] for value in served}.items() <= blaze.items()


def test_the_coded_domains_var_is_the_type_domain_export_spurs_tests_decode_with():
    """side_trails' Type is test_lib_spurs.py's whole domain but one label, and holds test_export_spurs.py's codes.

    test_lib_spurs.py labels code "2" "Signficant Non-Blaze", the misspelling
    60 features carry in place of a code (lib/spurs.py's TYPE_LITERAL_ALIASES).
    The live layer's domain, read 2026-10-02, spells it "Significant
    Non-Blaze", and the var follows the layer. No spur can differ for it:
    lib/spurs.decode_type reads a label only to turn a name back into its
    code, both spellings already decode to "2" through the aliases, and "2"
    is not SPUR_TYPE_CODE.
    """
    type_domain = _coded_domain("side_trails", "Type")
    assert LIB_SPURS_TYPE_DOMAIN["2"] == "Signficant Non-Blaze"
    assert type_domain == {**LIB_SPURS_TYPE_DOMAIN, "2": "Significant Non-Blaze"}
    assert EXPORT_SPURS_TYPE_DOMAIN.items() <= type_domain.items()


def test_the_coded_domains_var_holds_only_the_fields_the_exporters_decode():
    """export_trails.py decodes side_trails' Blaze and export_spurs.py its Type, so every row is pinned by a test above."""
    rows = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]["trail_lines_coded_domains"]
    assert {(source, field) for source, field, _code, _label in rows} == {("side_trails", "Blaze"), ("side_trails", "Type")}


def _columns(rows: list[dict], names: tuple[str, ...]) -> list[dict]:
    return [{name: row.get(name) for name in names} for row in rows]


def test_each_mile_axis_unit_tests_given_rows_are_the_previous_tests_expected_rows():
    """The four unit tests are one run of the axis, so a fix to one step's expected rows must reach the next step's input."""
    pieces = _columns(PIECES["expect"]["rows"], ("pre_calibration_order", "geom_5070_wkt"))
    for test in (MARKERS, CALIBRATION, HOLDOUT):
        assert _given(test, "int_trail_lines__mile_axis_pieces") == pieces, test["name"]
    pairs = _columns(MARKERS["expect"]["rows"], ("pre_calibration_order", "marker_row", "measure_mi", "snapped", "along_m"))
    for test in (CALIBRATION, HOLDOUT):
        assert _given(test, "int_trail_lines__mile_axis_markers") == pairs, test["name"]


def _segments_file(tmp_path: Path) -> Path:
    """The pieces unit test's segments as the GeoJSON export_elevation.py reads, in source_row order."""
    rows = sorted(_given(PIECES, "stg_atc__centerline_segments"), key=lambda row: row["source_row"])
    features = []
    for row in rows:
        geometry = None
        if row["geom"] is not None:
            geometry = {"type": "LineString", "coordinates": [list(xy) for xy in shapely_wkt.loads(row["geom"]).coords]}
        features.append({"type": "Feature", "properties": {"GlobalID": row["source_id"]}, "geometry": geometry})
    path = tmp_path / "centerline.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def _markers_file(tmp_path: Path) -> Path:
    rows = sorted(_given(MARKERS, "stg_atc__half_mile_markers"), key=lambda row: row["source_row"])
    features = [
        {
            "type": "Feature",
            "properties": {"Point_ID": int(row["source_id"]), "Measure": row["measure_mi"]},
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
        }
        for row in rows
    ]
    path = tmp_path / "half_mile_points_from_springer.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def _parts_meters() -> list[LineString]:
    rows = sorted(PIECES["expect"]["rows"], key=lambda row: row["pre_calibration_order"])
    return [shapely_wkt.loads(row["geom_5070_wkt"]) for row in rows]


def test_the_pieces_are_export_elevations_merged_ordered_and_oriented_parts(tmp_path, con):
    merged = export_elevation.load_merged_trail_line(con, _segments_file(tmp_path))
    merge_parts = list(merged.geoms) if isinstance(merged, MultiLineString) else [merged]
    ordered = export_elevation.ordered_oriented_parts(merged)
    in_metres = export_elevation.reproject_lines_to_meters(con, ordered)

    expected = sorted(PIECES["expect"]["rows"], key=lambda row: row["pre_calibration_order"])
    assert len(expected) == len(ordered)
    for row, part, part_m in zip(expected, ordered, in_metres):
        source = merge_parts[row["merge_part_index"] - 1]
        reversed_ = list(source.coords) != list(part.coords)
        assert reversed_ == row["reversed_by_straight_axis"], row["pre_calibration_order"]
        assert list(source.coords)[:: -1 if reversed_ else 1] == list(part.coords)
        # Coordinates to the bit, read back from the WKT the unit test holds the SQL to.
        assert list(shapely_wkt.loads(row["geom_wkt"]).coords) == list(part.coords)
        assert list(shapely_wkt.loads(row["geom_5070_wkt"]).coords) == list(part_m.coords)


def _python_pairs(con, tmp_path) -> list[dict]:
    """export_elevation's snap and its outright anchor, as (piece, marker, snapped, along) rows."""
    parts = _parts_meters()
    points, miles = export_elevation.load_half_mile_markers(con, _markers_file(tmp_path))
    snapped = export_elevation._snap_markers_to_parts(parts, points, miles)
    rows = []
    for index, part in enumerate(parts):
        pairs = snapped.get(index)
        if pairs:
            for along_m, mile in pairs:
                # The marker a pair came from: the Python keeps only (along, mile), so find it by mile.
                (marker_row,) = [row for row, m in enumerate(miles) if m == mile]
                rows.append(
                    {
                        "pre_calibration_order": index,
                        "marker_row": marker_row,
                        "snapped": True,
                        "along_m": along_m,
                        "measure_mi": float(mile),
                    }
                )
        else:
            nearest = int(STRtree(points).nearest(part))
            rows.append(
                {
                    "pre_calibration_order": index,
                    "marker_row": nearest,
                    "snapped": False,
                    "along_m": part.project(points[nearest]),
                    "measure_mi": float(miles[nearest]),
                }
            )
    return rows


def test_the_marker_pairs_are_export_elevations_snap_and_outright_anchor(tmp_path, con):
    """Which marker calibrates which piece, snapped or outright, and where along it, to the bit."""
    key = ("pre_calibration_order", "marker_row", "snapped", "along_m", "measure_mi")
    expected = _columns(MARKERS["expect"]["rows"], key)
    python = _python_pairs(con, tmp_path)
    assert sorted(python, key=lambda r: (r["pre_calibration_order"], r["along_m"], r["measure_mi"])) == sorted(
        expected, key=lambda r: (r["pre_calibration_order"], r["along_m"], r["measure_mi"])
    )


def test_the_calibration_is_export_elevations_calibrated_parts_in_their_order():
    """_calibrated_part over the unit test's own pairs, sorted by start mile: the same JSON to the bit."""
    parts = _parts_meters()
    pairs_by_piece: dict[int, list] = {}
    for row in _given(CALIBRATION, "int_trail_lines__mile_axis_markers"):
        pairs_by_piece.setdefault(row["pre_calibration_order"], []).append((row["along_m"], row["measure_mi"]))
    calibrated = []
    for index, part in enumerate(parts):
        cal, reversed_ = export_elevation._calibrated_part(part, sorted(pairs_by_piece[index]))
        calibrated.append((cal.start_mile, index, cal, reversed_, len(pairs_by_piece[index])))
    calibrated.sort(key=lambda item: item[0])  # stable, as calibrate_parts_to_markers' sort is

    expected = sorted(CALIBRATION["expect"]["rows"], key=lambda row: row["piece_id"])
    assert len(expected) == len(calibrated)
    for piece_id, (row, (start, index, cal, reversed_, count)) in enumerate(zip(expected, calibrated)):
        assert row["piece_id"] == piece_id and row["pre_calibration_order"] == index
        assert row["reversed_by_markers"] == reversed_ and row["anchor_count"] == count
        figures = json.loads(row["calibration_json"])
        assert figures == {
            "length_m": cal.line.length,
            "start_mile": start,
            "end_mile": cal.mile_at(cal.line.length),
            "anchor_along_mi": cal.alongs_mi.tolist(),
            "anchor_mile": cal.miles.tolist(),
        }, piece_id


def test_the_held_out_gate_is_export_elevations_marker_agreement_on_the_fixture(tmp_path, con):
    points, miles = export_elevation.load_half_mile_markers(con, _markers_file(tmp_path))
    agreement = export_elevation.measure_marker_agreement(_parts_meters(), points, miles)
    (row,) = HOLDOUT["expect"]["rows"]
    assert {name: row[name] for name in agreement} == agreement
    with pytest.raises(SystemExit, match=r"median 0\.119 mi > 0\.05"):
        export_elevation.require_marker_agreement(agreement)
    assert (row["median_within_gate"], row["p95_within_gate"], row["max_within_gate"]) == (False, True, True)


@pytest.mark.parametrize(
    ("test", "breaches"),
    [(HOLDOUT_P95, ("p95",)), (HOLDOUT_MAX, ("p95", "max"))],
    ids=["p95", "max"],
)
def test_the_held_out_gate_refuses_what_require_marker_agreement_refuses(test, breaches):
    """The straight 8,192 m piece: markers at whole metres, so the Python's project() and the SQL's along agree exactly."""
    (piece,) = _given(test, "int_trail_lines__mile_axis_pieces")
    rows = _given(test, "int_trail_lines__mile_axis_markers")
    points = [Point(row["along_m"], 0.0) for row in rows]
    miles = np.array([row["measure_mi"] for row in rows])
    agreement = export_elevation.measure_marker_agreement([shapely_wkt.loads(piece["geom_5070_wkt"])], points, miles)
    (row,) = test["expect"]["rows"]
    assert {name: row[name] for name in agreement} == agreement
    with pytest.raises(SystemExit) as refused:
        export_elevation.require_marker_agreement(agreement)
    # "...on held-out points: p95 0.810 mi > 0.25; max 1.328 mi > 1.0. Refusing..."
    message = str(refused.value).split("points: ", 1)[1].split(". Refusing", 1)[0]
    named = {breach.split()[0] for breach in message.split("; ")}
    assert named == set(breaches)
    assert {kind for kind in ("median", "p95", "max") if not row[f"{kind}_within_gate"]} == set(breaches)


# --- The A.T. models' unit tests, against the Python ---------------------------------
#
# models/intermediate/trail_lines/_trail_lines__unit_tests.yml holds the SQL to
# its expected rows; these hold each expected row to today's Python over the
# same given rows. Where the two answer differently on purpose, DELIBERATE names
# the row and the reason, and the comparison asserts the difference: a row that
# stops differing fails as "no longer deliberate", and a reason deleted from
# DELIBERATE fails as a difference.

UNIT_TESTS = DBT / "models" / "intermediate" / "trail_lines" / "_trail_lines__unit_tests.yml"
TESTS = Path(__file__).parent


@functools.cache
def _at_document() -> dict:
    return yaml.safe_load(UNIT_TESTS.read_text())


def _at_test(name: str) -> dict:
    (test,) = [test for test in _at_document()["unit_tests"] if test["name"] == name]
    return test


def _at_tests(model: str) -> list[dict]:
    return [test for test in _at_document()["unit_tests"] if test["model"] == model]


def _at_given(test: dict, model: str):
    """A versioned mart's given names its version, `ref('points_of_interest', v=1)` (check_contract_versions.py's
    rule 5)."""
    (given,) = [given for given in test["given"] if re.fullmatch(rf"ref\('{model}'(, v=\d+)?\)", given["input"])]
    return given["rows"]


def _expected(test: dict, key: str) -> dict:
    return {row[key]: row for row in test["expect"]["rows"]}


#: (unit test, row key) -> why the SQL's answer there is not the Python's.
DELIBERATE: dict[tuple[str, str], str] = {
    (
        "int_trail_lines__at_features_answers_what_resolve_feature_id_answers",
        "test_export_spurs::test_a_null_global_id_resolves_to_the_same_id_on_both_sides",
    ): (
        "TL05: the extract lands a feature's properties and not its GeoJSON id, so the SQL reads the OBJECTID in its "
        "place, equal to it on 3,025 of 3,025 centerline and 1,197 of 1,197 side-trail features (measured "
        "2026-10-02). This case builds the one shape ArcGIS never serves, an OBJECTID with no id, which the Python "
        "numbers by its place; both files still key the spur alike, since int_trail_lines__spurs reads "
        "int_trail_lines__at_features' id."
    ),
    (
        "int_trail_lines__at_chain_miles_read_a_shared_end_on_the_piece_it_begins",
        "centerline:chain:0",
    ): (
        "The axis tie (the axis_mile macro's header, @unvalidated): at a point where one piece ends and the next "
        "begins, STRtree's pick is its tree's visiting order, here the piece the point ends (10.144), and at the "
        "one live tie, near mile 1261, the piece it begins; the macro reads the next piece by rule (10.0). No "
        "trail_miles.json mile differs on ATC's live centerline (216,767 of 216,767, 2026-10-02). `mile` is a "
        "safety field: for the maintainer's decision at the go/no-go gate."
    ),
    (
        "int_trail_lines__at_overview_draws_nothing_where_the_centerline_may_not_publish",
        "",
    ): (
        "The publication rule: every A.T. file keeps only what its source may publish (int_sources__publication), "
        "which the Python reads nowhere. No difference while the four A.T. layers may publish (sources.json, "
        "2026-10-02)."
    ),
    (
        "int_trail_lines__club_stretches_attribute_nothing_where_the_centerline_may_not_publish",
        "",
    ): "The publication rule, for the centerline's attribution (as above).",
    (
        "int_trail_lines__club_stretches_publish_no_mile_where_the_markers_may_not",
        "",
    ): "The publication rule, for the markers' miles (as above).",
    (
        "int_trail_lines__club_names_name_no_club_from_a_layer_that_may_not_publish",
        "",
    ): "The publication rule, for the polygons' names (as above).",
    (
        "int_trail_lines__club_names_keep_the_lower_globalid_of_two_polygons_with_one_acronym",
        "PATC",
    ): (
        "Two polygons with one acronym: canonical_clubs() keeps the later in the layer's order, which "
        "stg_atc__club_sections does not carry, so the SQL keeps the lower GlobalID's and the warn test "
        "int_trail_lines__club_names_name_each_club_once says so. None of the 30 live polygons shares an acronym "
        "(2026-10-02)."
    ),
    (
        "int_trail_lines__at_side_trails_hold_only_the_spurs_trails_geojson_draws",
        "side_trails:undrawn",
    ): (
        "An improvement: spurs.json holds no record for a spur trails.geojson does not draw (no geometry, or past "
        "the corridor), which export_spurs.py writes and no phone can read, since client/src/lib/lineDetail.ts "
        "looks a spur up by the line it drew. None on ATC's live layers (784 of 784 spurs equal, 2026-10-02)."
    ),
    (
        "int_trail_lines__at_published_cuts_every_coordinate_and_never_degenerates_a_line",
        "centerline:chain:0",
    ): "Decision 8: trails.geojson's coordinates at 6 decimals, where export_trails.py writes GDAL's digits.",
    (
        "int_trail_lines__at_published_cuts_every_coordinate_and_never_degenerates_a_line",
        "side_trails:sql::every_coordinate_is_cut_to_six_decimals_as_round_cuts_it",
    ): "Decision 8 (as above).",
    ("parity.py trail_miles", "trails_sha256"): (
        "Derived: trail_miles.json's trails_sha256 is the hash of the trails.geojson written beside it, and "
        "decision 8 changes that file's bytes, so parity.py asks each file what the phone asks "
        "(client/src/lib/trailData.ts refuses miles whose hash is not the trails.geojson it holds) instead of "
        "comparing the two hashes."
    ),
    ("pub_club_sections", "source_edited"): (
        "Not built: club_sections.json's source_edited is {} until the extract lands each layer's "
        "editingInfo.dataLastEditDate (pub_club_sections' header), where export_club_sections.py dates each "
        "layer from fetch_all.py's manifest. The sheet omits the day, as it does for a release that carries none."
    ),
}


def _compare(test: str, key: str, python, sql, what: str = "") -> None:
    """Python's answer and the SQL's for one row: equal, or different for the reason DELIBERATE names."""
    if (test, key) in DELIBERATE:
        assert python != sql, f"{test} {key!r}{what} is no longer a deliberate difference: drop it from DELIBERATE"
    else:
        assert python == sql, f"{test} {key!r}{what}: Python {python!r}, SQL {sql!r}"


def _geojson(wkt: str | None) -> dict | None:
    """GeoJSON's {type, coordinates} for a POINT, LINESTRING or MULTILINESTRING's WKT, a one-vertex line and EMPTY
    parts included, both of which shapely refuses or reshapes and the raw layers can carry."""
    if wkt is None:
        return None
    kind, _, body = wkt.partition(" ")
    body = body.strip()

    def points(text: str) -> list[list[float]]:
        text = text.strip()
        return [] if text in ("", "EMPTY") else [[float(value) for value in pair.split()] for pair in text.split(",")]

    if kind == "POINT":
        return {"type": "Point", "coordinates": points(body.strip("()"))[0]}
    if kind == "LINESTRING":
        return {"type": "LineString", "coordinates": points("" if body == "EMPTY" else body[1:-1])}
    assert kind == "MULTILINESTRING", wkt
    parts = [] if body == "EMPTY" else [points(match.group(1) or "") for match in re.finditer(r"EMPTY|\(([^()]*)\)", body[1:-1])]
    return {"type": "MultiLineString", "coordinates": parts}


def _coords(wkt: str) -> list:
    return _geojson(wkt)["coordinates"]


def _axis(test: dict) -> list:
    """The unit test's int_trail_lines__mile_axis rows, its `format: sql` select run, as export_elevation's
    CalibratedPart in piece_id order: what calibrated_trail_axis returns."""
    con = spatial_connection()
    rows = con.execute(
        "select st_astext(geom_5070), anchor_along_mi, anchor_mile from ("
        + _at_given(test, "int_trail_lines__mile_axis")
        + ") order by piece_id"
    ).fetchall()
    con.close()
    return [
        export_elevation.CalibratedPart(shapely_wkt.loads(line), np.array(alongs), np.array(miles))
        for line, alongs, miles in rows
    ]


# --- which pytest cases the unit tests stand for -------------------------------------

#: The pytest files pipeline/ELT.md's trail_lines ledger lists against tl-at's
#: rows (TL01, TL04, TL05, TL14-TL17, TL22, TL24-TL29). export_nearby_trails
#: is the network's (tl-net), and lib_arcgis the live domain call TL02's var
#: replaces in SQL, which stays at the edge for every other caller.
LEDGER_FILES = (
    "test_export_trails",
    "test_lib_feature_id",
    "test_lib_corridor",
    "test_simplify_trails",
    "test_lib_club_sections",
    "test_export_club_sections",
    "test_lib_spurs",
    "test_export_spurs",
)
CORRIDOR_NETWORK = "lib/corridor.py's network ring (#1016), which the POI clip reads (the poi family), not TL14's A.T. corridor"
NOT_SOURCE_EDITED = "source_edited, not built (DELIBERATE: pub_club_sections source_edited)"
#: Every ledger-listed case no unit test names, and where its rule went instead.
ELSEWHERE: dict[str, str] = {
    "test_export_trails::test_export_trails_decodes_side_trails_blaze_field_via_the_real_coded_domain": (
        "int_trail_lines__blazes (tl-net): its unit test decodes against int_trail_lines__coded_domains"
    ),
    "test_export_trails::test_export_trails_applies_centerlines_flat_default_with_no_blaze_field": (
        "int_trail_lines__blazes (tl-net): the centerline's blaze_default row of its unit test"
    ),
    "test_export_trails::test_export_trails_warns_on_a_feature_that_fails_to_decode": (
        "int_trail_lines__blazes (tl-net): its unit test's undecoded rows, and its warn test"
    ),
    "test_export_trails::test_export_trails_writes_a_sha256_hash_for_the_trails_artifact": (
        "stage 4: a file's hash is publish's; trail_miles.json's trails_sha256 is pub_trail_miles' (DELIBERATE)"
    ),
    "test_export_trails::test_export_trails_exits_nonzero_when_a_source_returns_zero_features": (
        "data test: int_trail_lines__at_sources' relationships_where test (fail_if_incomplete) stops the build"
    ),
    "test_export_trails::test_export_trails_warning_names_the_fallback_id_when_a_decode_failure_coincides_with_a_null_global_id": (
        "a warning's words: dbt lists a warn test's failing rows, the decode warning's with trail_segment_key"
    ),
    "test_export_trails::test_the_manifest_records_the_pre_merge_segment_count": (
        "int_trail_lines__at_chains' part_count, 2 in its touching-segments unit test; the manifest is stage 4's"
    ),
    "test_export_trails::test_the_export_publishes_the_overview_beside_the_full_line": (
        "pub_trails_overview and its exposure trails_overview_geojson; the manifest entry is stage 4's"
    ),
    "test_export_trails::test_a_vertex_mile_is_the_same_measurement_a_poi_gets": (
        "by construction: every A.T. mile, a POI's included, comes off the one axis_mile macro"
    ),
    "test_export_trails::test_a_multilinestring_record_carries_one_list_per_part": (
        "data test int_trail_lines__at_chains_are_linestrings: no MultiLineString reaches the miles"
    ),
    "test_export_trails::test_batched_vertex_miles_equal_the_one_part_at_a_time_miles_to_the_bit": (
        "stays: the Python's batch against its own loop"
    ),
    "test_export_trails::test_no_markers_means_no_miles_and_a_loud_line": (
        "data test int_trail_lines__mile_axis_has_a_piece, error: the build stops, where the Python held back "
        "trail_miles.json alone"
    ),
    "test_lib_corridor::test_build_corridor_populates_a_single_non_empty_polygon": (
        "data tests on int_trail_lines__corridor (a unit test cannot hold its GEOMETRY): non-empty, a polygon, one row"
    ),
    "test_lib_corridor::test_build_corridor_area_is_plausible_for_a_30_mile_buffer_around_the_fixture_line": (
        "data test int_trail_lines__corridor_holds_a_buffer_disc"
    ),
    "test_lib_corridor::test_build_corridor_keeps_the_result_in_the_source_hemisphere_not_axis_swapped": (
        "data test int_trail_lines__corridor_lies_where_the_trail_does"
    ),
    "test_lib_corridor::test_no_network_path_builds_the_corridor_it_always_built": (
        "by construction: int_trail_lines__corridor is the A.T.-only corridor, with no network path"
    ),
    **{
        f"test_lib_corridor::{case}": CORRIDOR_NETWORK
        for case in (
            "test_the_corridor_reaches_ground_only_a_network_line_touches",
            "test_the_widening_still_holds_the_at_corridor",
            "test_the_polygon_stays_the_at_s_and_the_ring_is_a_join",
            "test_the_ring_keeps_a_point_inside_it_and_drops_one_just_past_it",
            "test_keep_within_corridor_answers_many_rows_at_once_with_their_own_ids",
            "test_the_network_ring_is_narrow_rather_than_thirty_miles",
            "test_the_ring_is_wider_than_the_gate_that_has_to_pass_through_it",
            "test_an_empty_network_artifact_is_not_a_network",
            "test_a_missing_network_artifact_is_not_a_network",
            "test_count_features_survives_an_artifact_with_no_features",
        )
    },
    "test_simplify_trails::test_default_tolerance_is_one_metre": (
        "the var, pinned to DEFAULT_SIMPLIFY_TOLERANCE_M by test_the_at_line_vars_are_export_trails_constants"
    ),
    "test_simplify_trails::test_default_tolerance_stays_under_one_screen_pixel_at_max_zoom": (
        "stays: the constant's own property, with the var pinned to the constant"
    ),
    "test_simplify_trails::test_simplify_rejects_a_negative_tolerance": (
        "the simplified_in_metres macro's error(), run by test_the_simplify_macro_refuses_a_negative_tolerance"
    ),
    "test_simplify_trails::test_batched_simplify_records_writes_what_the_per_record_loop_wrote": (
        "stays: the Python's batch against its own loop"
    ),
    "test_simplify_trails::test_drawable_all_answers_what_has_drawable_geometry_answers": (
        "stays: the Python's batch predicate against its own; the unit test's predicate rows hold line_is_drawable"
    ),
    "test_lib_club_sections::test_the_half_width_constant_is_half_the_milepost_spacing": (
        "stays: the constant's own test, with the var pinned to it by test_the_club_vars_are_lib_club_sections_constants"
    ),
    "test_export_club_sections::test_the_manifest_path_resolves_from_any_cwd_and_main_returns_the_manifest": (
        "stays: the exporter's manifest, stage 4's in the dbt path"
    ),
    **{
        f"test_export_club_sections::{case}": NOT_SOURCE_EDITED
        for case in (
            "test_reads_both_dates_the_issue_measured_by_hand",
            "test_a_layer_with_no_recorded_date_is_absent_rather_than_null",
            "test_no_manifest_at_all_dates_nothing_rather_than_failing",
            "test_an_unreadable_manifest_dates_nothing_rather_than_crashing_the_export",
            "test_a_sentinel_epoch_publishes_no_date_rather_than_1969",
            "test_a_date_that_is_not_a_number_publishes_nothing",
            "test_the_dates_are_keyed_by_layer_so_a_shared_layer_carries_one_date",
        )
    },
    "test_export_club_sections::test_the_published_sources_block_keeps_its_string_values": (
        "the contract: pub_club_sections' `sources` is struct(attribution varchar, names varchar, miles varchar)"
    ),
    **{
        f"test_lib_spurs::{case}": "stays: distance_m()'s own properties; every metre the spur rows publish holds the SQL's expression to it"
        for case in (
            "test_distance_is_symmetric",
            "test_a_degree_of_latitude_is_about_111_km",
            "test_a_degree_of_longitude_shrinks_with_latitude",
        )
    },
    "test_export_spurs::test_destination_pois_are_read_from_the_published_files_not_the_raw_ones": (
        "by construction: int_trail_lines__spur_destinations reads the points_of_interest mart, the published POIs"
    ),
    "test_export_spurs::test_the_real_exporter_writes_what_the_real_reader_looks_for": (
        "by construction: one model reads the other, with no file name between them"
    ),
    "test_export_spurs::test_every_poi_type_is_classified_as_a_destination_or_explicitly_not": (
        "the var trail_lines_spur_destination_poi_types, pinned by test_the_spur_vars_are_lib_spurs_constants"
    ),
    "test_export_spurs::test_the_doc_names_every_type_the_code_classifies": "stays: features/SPUR_TRAILS.md against the constants",
    "test_export_spurs::test_the_two_lists_do_not_overlap": "stays: export_spurs.py's two constants",
    "test_export_spurs::test_the_output_is_keyed_by_id_so_the_client_can_look_one_up": (
        "pub_spurs' shape, held by parity.py's spurs family"
    ),
    "test_export_spurs::test_a_run_without_the_half_mile_markers_fails_instead_of_publishing_unmiled_spurs": (
        "data test int_trail_lines__mile_axis_has_a_piece, error"
    ),
    "test_export_spurs::test_a_run_with_missing_inputs_fails_instead_of_publishing_nothing": (
        "the sources' and staging's own tests, and int_trail_lines__at_sources' relationships_where test"
    ),
    "test_export_spurs::test_a_run_with_no_published_pois_warns_rather_than_resolving_nothing_quietly": (
        "warn test int_trail_lines__spur_destinations_warns_when_no_poi_is_published"
    ),
}
CASE = re.compile(r"(?:tests/)?(test_[a-z0-9_]+)(?:\.py)?::(test_[a-z0-9_]+)")


def _named_cases() -> set[str]:
    """Every `<pytest file>::<case>` the unit tests name, as a row key or in a description."""
    text = UNIT_TESTS.read_text()
    return {f"{file}::{name}" for file, name in CASE.findall(text)}


def _ledger_cases() -> set[str]:
    cases = set()
    for file in LEDGER_FILES:
        source = (TESTS / f"{file}.py").read_text()
        cases |= {f"{file}::{name}" for name in re.findall(r"^def (test_\w+)", source, re.MULTILINE)}
    return cases


def test_every_case_a_unit_test_names_is_a_real_pytest_case():
    for case in _named_cases():
        file, name = case.split("::")
        assert re.search(rf"^def {name}\(", (TESTS / f"{file}.py").read_text(), re.MULTILINE), case


def test_every_ledger_listed_case_has_a_home():
    """pipeline/ELT.md's "Tests move with their rule": each case beside its unit test, or the reason it has none."""
    homeless = _ledger_cases() - _named_cases() - set(ELSEWHERE)
    assert not homeless, f"no unit test names these and ELSEWHERE does not place them: {sorted(homeless)}"
    assert not set(ELSEWHERE) & _named_cases(), "a case both a unit test names and ELSEWHERE places"
    assert set(ELSEWHERE) <= _ledger_cases(), sorted(set(ELSEWHERE) - _ledger_cases())


def test_every_deliberate_difference_names_a_unit_test_or_a_file_that_exists():
    names = {test["name"] for test in _at_document()["unit_tests"]}
    for test, _key in DELIBERATE:
        assert test in names or test in ("parity.py trail_miles", "pub_club_sections"), test


# --- int_trail_lines__at_features, __at_sources, __at_clipped ------------------------


def test_the_at_features_rows_are_resolve_feature_ids_answers():
    test = _at_test("int_trail_lines__at_features_answers_what_resolve_feature_id_answers")
    expected = _expected(test, "trail_segment_key")
    order = {row["source_key"]: row["file_row"] for row in _at_given(test, "int_trail_lines__at_sources")}
    rows = [("centerline", row) for row in _at_given(test, "stg_atc__centerline_segments")]
    rows += [("side_trails", row) for row in _at_given(test, "stg_atc__side_trails")]
    assert sorted(expected) == sorted(row["trail_segment_key"] for _, row in rows)
    for source, row in rows:
        key = row["trail_segment_key"]
        properties = {"GlobalID": row.get("source_id")}
        feature = {}
        if source == "side_trails" and row.get("objectid") is not None:
            # ArcGIS serves the OBJECTID as the feature's GeoJSON id; the export_spurs case builds a feature
            # with the OBJECTID as a property and no id at all.
            if key.startswith("test_export_spurs::"):
                properties["OBJECTID"] = row["objectid"]
            else:
                feature["id"] = row["objectid"]
        resolved = str(resolve_feature_id(source, feature, properties, row["source_row"]))
        _compare(test["name"], key, resolved, expected[key]["feature_id"])
        assert expected[key]["trail_line_id"] == f"{source}:{expected[key]['feature_id']}", key
        assert expected[key]["source_order"] == order[source], key
        geometry = _geojson(row.get("geom"))
        is_line = geometry is not None and geometry["type"] in ("LineString", "MultiLineString")
        assert expected[key]["has_line_geometry"] == is_line, key


def test_the_at_sources_rows_are_load_line_sources_answers(tmp_path):
    test = _at_test("int_trail_lines__at_sources_answers_what_load_line_sources_answers")
    entries = sorted(_at_given(test, "stg_registry__sources"), key=lambda row: row["file_row"])
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [json.loads(row["entry"]) for row in entries]}))
    python = [source["key"] for source in export_trails.load_line_sources(path)]
    rows = sorted(test["expect"]["rows"], key=lambda row: row["file_row"])
    assert [row["source_key"] for row in rows] == python
    for row in rows:
        entry = json.loads(next(e["entry"] for e in entries if e["source_key"] == row["source_key"]))
        assert (row["blaze_field"], row["blaze_default"]) == (entry.get("blaze_field"), entry.get("blaze_default"))
    # export_trails.main() reads data/raw/<key>.geojson; the SQL reads the two staging models it has.
    assert {row["source_key"] for row in rows if row["staged"]} == {"centerline", "side_trails"}


def test_the_at_clipped_rows_are_clip_to_corridors_answers():
    """clip_to_corridor()'s ST_Intersects, as shapely's: a line touching the corridor kept whole."""
    test = _at_test("int_trail_lines__at_clipped_keeps_whole_what_touches_the_corridor")
    ((corridor_row,),) = [_at_given(test, "int_trail_lines__corridor")]
    box = shapely_wkt.loads(corridor_row["geom"])
    kept = {
        row["trail_segment_key"]: row["geom_wkt"]
        for row in _at_given(test, "int_trail_lines__at_features")
        if row["has_line_geometry"] and shapely_wkt.loads(row["geom_wkt"]).intersects(box)
    }
    assert {row["trail_segment_key"]: row["geom_wkt"] for row in test["expect"]["rows"]} == kept


# --- int_trail_lines__at_simplified (TL15) -------------------------------------------


def _simplified_tests() -> list[dict]:
    return _at_tests("int_trail_lines__at_simplified")


def test_the_at_simplified_rows_are_simplify_records_answers():
    """simplify_records() at each test's tolerance (the var, or its override), every vertex to the bit, and
    `simplified` true exactly where the pass's own result was drawable."""
    for test in _simplified_tests():
        tolerance = (
            (test.get("overrides") or {})
            .get("vars", {})
            .get("trail_lines_simplify_tolerance_m", export_trails.DEFAULT_SIMPLIFY_TOLERANCE_M)
        )
        given = _at_given(test, "int_trail_lines__at_clipped")
        records = [
            {
                "id": row["trail_line_id"],
                "source": row["source_key"],
                "name": row["name"],
                "blaze_color": row["blaze_color"],
                "wkt": row["geom_wkt"],
            }
            for row in given
        ]
        out = export_trails.simplify_records(records, tolerance)
        expected = _expected(test, "trail_segment_key")
        assert sorted(expected) == sorted(row["trail_segment_key"] for row in given), test["name"]
        for row, record in zip(given, out):
            want = expected[row["trail_segment_key"]]
            _compare(test["name"], row["trail_segment_key"], _coords(record["wkt"]), _coords(want["geom_wkt"]))
            assert want["full_geom_wkt"] == row["geom_wkt"] or _coords(want["full_geom_wkt"]) == _coords(row["geom_wkt"])
            assert (want["name"], want["blaze_color"], want["length_ft"]) == (row["name"], row["blaze_color"], row["length_ft"])
            if tolerance:
                reduced = shapely_transform(
                    export_trails._TO_GEOGRAPHIC,
                    shapely_transform(export_trails._TO_METRIC, shapely_wkt.loads(row["geom_wkt"])).simplify(
                        tolerance, preserve_topology=False
                    ),
                )
                assert want["simplified"] == (not reduced.is_empty and export_trails._has_drawable_geometry(reduced))


def test_the_tolerance_cases_assert_what_their_pytest_cases_assert():
    def line(name: str, key: str) -> list:
        return _coords(_expected(_at_test(name), "trail_segment_key")[key]["geom_wkt"])

    larger = "test_simplify_trails::test_a_larger_tolerance_removes_more"
    fine = line("int_trail_lines__at_simplified_at_a_tolerance_of_0_5_m", larger)
    coarse = line("int_trail_lines__at_simplified_at_a_tolerance_of_5_0_m", larger)
    assert len(coarse) < len(fine)
    zero = _at_test("int_trail_lines__at_simplified_at_a_tolerance_of_0_m")
    ((given,),) = [_at_given(zero, "int_trail_lines__at_clipped")]
    assert _coords(_expected(zero, "trail_segment_key")[given["trail_segment_key"]]["geom_wkt"]) == _coords(given["geom_wkt"])
    two = line(
        "int_trail_lines__at_simplified_at_a_tolerance_of_1000_m",
        "test_simplify_trails::test_simplify_never_degenerates_a_line_below_two_points",
    )
    assert len(two) == 2
    default = "int_trail_lines__at_simplified_answers_what_simplify_records_answers"
    rows = {row["trail_segment_key"]: row for row in _at_given(_at_test(default), "int_trail_lines__at_clipped")}
    ends = "test_simplify_trails::test_simplify_preserves_both_endpoints_exactly"
    drawn, surveyed = line(default, ends), _coords(rows[ends]["geom_wkt"])
    assert drawn[0] == pytest.approx(surveyed[0], abs=1e-9) and drawn[-1] == pytest.approx(surveyed[-1], abs=1e-9)
    bounded = "test_simplify_trails::test_simplify_never_moves_the_line_further_than_the_tolerance"
    moved = LineString(_coords(rows[bounded]["geom_wkt"])).hausdorff_distance(LineString(line(default, bounded)))
    assert moved * 111_320.0 <= 1.5
    fewer = "test_simplify_trails::test_simplify_removes_vertices_finer_than_the_tolerance"
    assert len(line(default, fewer)) < len(_coords(rows[fewer]["geom_wkt"]))
    sparse = "test_simplify_trails::test_simplify_leaves_an_already_sparse_line_alone"
    assert len(line(default, sparse)) == 3


def _simplify_macro(geom: str, tolerance: str) -> str:
    """macros/trail_line_geometry.sql's simplified_in_metres, its two arguments put in by hand."""
    text = (DBT / "macros" / "trail_line_geometry.sql").read_text()
    body = text.split("{% macro simplified_in_metres(geom, tolerance) -%}", 1)[1].split("{%- endmacro %}", 1)[0]
    return body.replace("{{ geom }}", geom).replace("{{ tolerance }}", tolerance)


def test_the_simplify_macro_refuses_a_negative_tolerance():
    """test_simplify_trails.py::test_simplify_rejects_a_negative_tolerance, against the macro's own text, and its
    zero passthrough."""
    import duckdb

    con = spatial_connection()
    line = "st_geomfromtext('LINESTRING (-74 41, -74.00001 41.00001, -74 41.0001)')"
    with pytest.raises(duckdb.InvalidInputException, match="tolerance must be >= 0"):
        con.execute(f"select {_simplify_macro(line, '-1')}").fetchall()
    (untouched,) = con.execute(f"select st_astext({_simplify_macro(line, '0')})").fetchone()
    assert untouched == "LINESTRING (-74 41, -74.00001 41.00001, -74 41.0001)"
    con.close()


# --- int_trail_lines__at_chains, __at_chain_miles (TL16, TL22) -----------------------


def test_the_at_chains_rows_are_merge_chain_records_answers():
    for test in _at_tests("int_trail_lines__at_chains"):
        given = sorted(
            _at_given(test, "int_trail_lines__at_simplified"), key=lambda row: (row["source_order"], row["source_row"])
        )
        records = [
            {
                "id": row["trail_line_id"],
                "source": row["source_key"],
                "name": row["name"],
                "blaze_color": row["blaze_color"],
                "wkt": row["geom_wkt"],
            }
            for row in given
        ]
        merged, stats = export_trails.merge_chain_records(records)
        chains = [record for record in merged if ":chain:" in record["id"]]
        expected = sorted(test["expect"]["rows"], key=lambda row: row["chain_index"])
        assert [record["id"] for record in chains] == [row["trail_line_id"] for row in expected], test["name"]
        for record, row in zip(chains, expected):
            assert (record["name"], record["blaze_color"]) == (row["name"], row["blaze_color"]), test["name"]
            assert _coords(record["wkt"]) == _coords(row["geom_wkt"]), test["name"]
        if len(expected) == 1:
            assert expected[0]["part_count"] == stats["centerline"]["constituents"], test["name"]


def test_the_at_chain_miles_rows_are_vertex_miles_answers(monkeypatch):
    """export_trails.vertex_miles() itself, on the unit test's own axis: each chain's miles and its backward steps."""
    import duckdb

    for test in _at_tests("int_trail_lines__at_chain_miles"):
        monkeypatch.setattr(export_trails, "calibrated_trail_axis", lambda con, centerline, markers, axis=_axis(test): axis)
        chains = _at_given(test, "int_trail_lines__at_chains")
        records = [{"id": row["trail_line_id"], "source": "centerline", "wkt": row["geom_wkt"]} for row in chains]
        miles, _ = export_trails.vertex_miles(duckdb.connect(), records, Path("unused"), Path("unused"))
        for key, row in _expected(test, "trail_line_id").items():
            _compare(test["name"], key, miles[key], json.loads(row["vertex_miles_json"]))
            assert row["monotonic_breaks"] == export_trails._monotonic_breaks(np.array(json.loads(row["vertex_miles_json"]))), key


# --- int_trail_lines__at_overview (TL17) ---------------------------------------------


def test_the_at_overview_rows_are_write_overviews_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(export_trails, "OUT_DIR", tmp_path)
    for test in _at_tests("int_trail_lines__at_overview"):
        given = sorted(
            _at_given(test, "int_trail_lines__at_simplified"), key=lambda row: (row["source_order"], row["source_row"])
        )
        records = [
            {
                "id": row["trail_line_id"],
                "source": row["source_key"],
                "name": None,
                "blaze_color": "White",
                "wkt": row["geom_wkt"],
            }
            for row in given
        ]
        export_trails.write_overview(records)
        body = json.loads((tmp_path / "trails_overview.geojson").read_text())
        python = body["features"][0]["geometry"]["coordinates"]
        sql = [json.loads(row["coordinates_json"]) for row in sorted(test["expect"]["rows"], key=lambda row: row["line_order"])]
        _compare(test["name"], "", python, sql)
    no_further = _at_test("int_trail_lines__at_overview_no_overview_vertex_is_further_from_the_surveyed_line_than_it_claims")
    ((surveyed,),) = [_at_given(no_further, "int_trail_lines__at_simplified")]
    ((drawn,),) = [no_further["expect"]["rows"]]
    metric = [
        shapely_transform(export_trails._TO_METRIC, line)
        for line in (LineString(_coords(surveyed["geom_wkt"])), LineString(json.loads(drawn["coordinates_json"])))
    ]
    assert metric[1].hausdorff_distance(metric[0]) < export_trails.OVERVIEW_SIMPLIFY_TOLERANCE_M + 20
    fraction = _at_test("int_trail_lines__at_overview_is_a_fraction_of_the_line_it_sketches")
    ((line,),) = [_at_given(fraction, "int_trail_lines__at_simplified")]
    ((sketch,),) = [fraction["expect"]["rows"]]
    assert len(json.loads(sketch["coordinates_json"])) < len(_coords(line["geom_wkt"])) / 4


# --- int_trail_lines__spurs, __at_side_trails (TL27-TL29) ----------------------------


def _spur_python(test: dict, monkeypatch) -> dict[str, dict]:
    """export_spurs.build_spur_records() and attach_junction_miles() over the unit test's own rows, its mile axis
    standing in for calibrated_trail_axis."""
    features = _at_given(test, "int_trail_lines__at_features")
    side_trails = [
        {
            "properties": {
                "GlobalID": row["trail_line_id"].split(":", 1)[1],
                "Type": row["trail_type"],
                "Name": row["name"],
                "Length_Ft": row["length_ft"],
            },
            "geometry": _geojson(row["geom_wkt"]),
        }
        for row in sorted(features, key=lambda row: row["source_row"])
        if row["source_key"] == "side_trails"
    ]
    centerline = [{"geometry": _geojson(row["geom_wkt"])} for row in features if row["source_key"] == "centerline"]
    destinations = sorted(_at_given(test, "int_trail_lines__spur_destinations"), key=lambda row: row["destination_order"])
    pois = [
        {"id": row["poi_id"], "lat": row["latitude"], "lon": row["longitude"]}
        for row in destinations
        if row["poi_type"] in export_spurs.DESTINATION_POI_TYPES
    ]
    domain = {row["code"]: row["label"] for row in _at_given(test, "int_trail_lines__coded_domains")} or None
    records = export_spurs.build_spur_records(side_trails, centerline, pois, domain)
    monkeypatch.setattr(export_spurs, "calibrated_trail_axis", lambda con, c, m: _axis(test))
    export_spurs.attach_junction_miles(records, Path("unused"), Path("unused"))
    return records


def test_the_spur_rows_are_build_spur_records_answers(monkeypatch):
    for test in _at_tests("int_trail_lines__spurs"):
        records = _spur_python(test, monkeypatch)
        features = {row["trail_segment_key"]: row for row in _at_given(test, "int_trail_lines__at_features")}
        domain = {row["code"]: row["label"] for row in _at_given(test, "int_trail_lines__coded_domains")} or None
        for key, row in _expected(test, "trail_segment_key").items():
            raw = features[key]["trail_type"]
            assert row["type_code"] == lib_spurs.decode_type(raw, domain), key
            assert row["type_undecodable"] == (row["type_code"] is None and raw is not None and bool(str(raw).strip())), key
            assert row["is_spur"] == (row["trail_line_id"] in records), key
            if row["is_spur"]:
                _compare(test["name"], key, records[row["trail_line_id"]], json.loads(row["spur_record_json"]))
        resolved = {json.dumps(sorted(json.loads(row["spur_record_json"]))) for row in test["expect"]["rows"] if row["is_spur"]}
        assert len(resolved) == 1, "a spur record without one of the keys every other carries"


def test_the_spur_destinations_are_load_destination_pois_answers(tmp_path, monkeypatch):
    """export_poi.write_poi_type() writes the unit test's poi_<type>.geojson rows, each file in its record order,
    and load_destination_pois() reads them back: the same POIs, in the same order, at the same lat and lon to the
    bit, GDAL's printing included."""
    import export_poi

    test = _at_test("int_trail_lines__spur_destinations_answer_what_load_destination_pois_answers")
    rows = [row for row in _at_given(test, "points_of_interest") if row["phone_files"] == "poi_by_type"]
    monkeypatch.setattr(export_poi, "OUT_DIR", tmp_path)
    con = spatial_connection()
    for poi_type in sorted({row["poi_type"] for row in rows}):
        records = [
            {
                "id": row["poi_id"],
                "poi_type": poi_type,
                "trail_id": "AT",
                "source": "atc_test",
                "source_feature_id": row["poi_id"],
                "name": row["poi_id"],
                "lat": row["lat"],
                "lon": row["lon"],
                "confidence": "high",
            }
            for row in sorted(rows, key=lambda row: row["record_order"])
            if row["poi_type"] == poi_type
        ]
        export_poi.write_poi_type(con, poi_type, records)
    con.close()
    python = [(poi["id"], poi["lat"], poi["lon"]) for poi in export_spurs.load_destination_pois(tmp_path)]
    sql = [
        (row["poi_id"], row["latitude"], row["longitude"])
        for row in sorted(test["expect"]["rows"], key=lambda row: row["destination_order"])
    ]
    assert python == sql


def test_spurs_json_holds_only_the_spurs_trails_geojson_draws():
    """export_spurs.main() writes every record build_spur_records() returns, every is_spur row of
    int_trail_lines__spurs; spurs.json is written from the side trails trails.geojson draws."""
    test = _at_test("int_trail_lines__at_side_trails_hold_only_the_spurs_trails_geojson_draws")
    python = {row["trail_line_id"] for row in _at_given(test, "int_trail_lines__spurs") if row["is_spur"]}
    sql = {row["trail_line_id"] for row in test["expect"]["rows"] if row["is_spur"]}
    for key in sorted(python | sql):
        _compare(test["name"], key, key in python, key in sql)


# --- int_trail_lines__at_published (decision 8) --------------------------------------


def test_the_at_published_rows_are_rounded_geometrys_answers():
    """Every line is _rounded_geometry()'s cut, the never-degenerate rule included; where that is not the line
    export_trails.py writes, DELIBERATE says decision 8. Chains first, then side trails in the layer's order."""
    test = _at_test("int_trail_lines__at_published_cuts_every_coordinate_and_never_degenerates_a_line")
    lines = {row["trail_line_id"]: row for row in _at_given(test, "int_trail_lines__at_chain_miles")}
    lines |= {row["trail_line_id"]: row for row in _at_given(test, "int_trail_lines__at_side_trails")}
    side = sorted(_at_given(test, "int_trail_lines__at_side_trails"), key=lambda row: (row["source_order"], row["source_row"]))
    chains = sorted(_at_given(test, "int_trail_lines__at_chain_miles"), key=lambda row: row["chain_index"])
    expected = sorted(test["expect"]["rows"], key=lambda row: row["feature_order"])
    assert [row["trail_line_id"] for row in expected] == [row["trail_line_id"] for row in chains + side]
    for row in expected:
        geometry = shapely_wkt.loads(lines[row["trail_line_id"]]["geom_wkt"])
        published = json.loads(row["geom_geojson"])
        assert published == export_nearby_trails._rounded_geometry(geometry), row["trail_line_id"]
        uncut = json.loads(json.dumps(shapely.geometry.mapping(geometry)))
        _compare(test["name"], row["trail_line_id"], uncut, published, " (export_trails.py's own digits)")
        is_side = row["trail_line_id"].startswith("side_trails:")
        assert (row["monotonic_breaks"] is None) == is_side, row["trail_line_id"]
        assert row["line_kind"] == (
            "centerline" if not is_side else "spur" if lines[row["trail_line_id"]]["is_spur"] else "side_trail"
        )


# --- the club sections (TL24-TL26) ---------------------------------------------------


def _club_python(test: dict) -> list[tuple[float, float, str | None]]:
    """export_club_sections' attribution and lib/club_sections.build_stretches over a club_stretches test's rows:
    (start, end, acronym) for every run, south to north."""
    segments = sorted(_at_given(test, "stg_atc__centerline_segments"), key=lambda row: row["source_row"])
    centerline = [{"properties": {"Acronym": row["club_acronym"]}, "geometry": _geojson(row["geom"])} for row in segments]
    markers = sorted(_at_given(test, "stg_atc__half_mile_markers"), key=lambda row: row["source_row"])
    mileposts = [
        {
            "properties": {"Measure": row["measure_mi"]},
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
        }
        for row in markers
    ]
    attributed = export_club_sections.attribute_mileposts(mileposts, export_club_sections.build_club_index(centerline))
    runs = lib_club_sections.build_stretches(attributed)
    return sorted((start, end, acronym) for acronym, spans in runs.items() for start, end in spans), attributed


def test_the_club_stretches_rows_are_build_stretches_answers():
    for test in _at_tests("int_trail_lines__club_stretches"):
        python, _ = _club_python(test)
        rows = sorted(test["expect"]["rows"], key=lambda row: row["run_order"])
        sql = [
            (json.loads(row["stretch_json"])["start_mile"], json.loads(row["stretch_json"])["end_mile"], row["acronym"])
            for row in rows
        ]
        assert [row["run_order"] for row in rows] == list(range(1, len(rows) + 1)), test["name"]
        _compare(test["name"], "", python, sql)


def _names_python(test: dict) -> dict:
    polygons = _at_given(test, "stg_atc__club_sections")
    features = [
        {"properties": {"ACROYNM": row["club_acronym"], "TRAIL_CLUB": row["trail_club"], "REGION": row.get("region")}}
        for row in polygons
    ]
    return lib_club_sections.canonical_clubs(features)


def test_the_club_names_rows_are_canonical_clubs_answers():
    for test in _at_tests("int_trail_lines__club_names"):
        python = _names_python(test)
        sql = _expected(test, "acronym")
        for acronym in sorted(python.keys() | sql.keys()):
            want = sql.get(acronym)
            _compare(
                test["name"],
                acronym if want and want["polygon_count"] > 1 else "",
                python.get(acronym),
                want and {"name": want["club_name"], "region": want["region"]},
            )


def test_the_club_sections_rows_are_assembles_answers():
    """Each club_sections test is given exactly its two feeder tests' expected rows, and assemble() over the
    feeders' own given rows is its answer."""
    for test in _at_tests("int_trail_lines__club_sections"):
        label = test["name"].removeprefix("int_trail_lines__club_sections_")
        stretches = _at_test(f"int_trail_lines__club_stretches_for_{label}")
        names = _at_test(f"int_trail_lines__club_names_for_{label}")
        assert _at_given(test, "int_trail_lines__club_stretches") == stretches["expect"]["rows"], label
        assert _at_given(test, "int_trail_lines__club_names") == names["expect"]["rows"], label
        _, attributed = _club_python(stretches)
        clubs, unattributed = lib_club_sections.assemble(attributed, _names_python(names))
        python = {
            club.acronym: {
                "club_name": club.name,
                "region": club.region,
                "miles": round(club.miles, 1),
                "stretches": [{"start_mile": start, "end_mile": end} for start, end in club.stretches],
                "club_order": order,
            }
            for order, club in enumerate(clubs)
        }
        rows = _expected(test, "section_key")
        sql = {
            key: {
                "club_name": row["club_name"],
                "region": row["region"],
                "miles": row["miles"],
                "stretches": json.loads(row["stretches_json"]),
                "club_order": row["club_order"],
            }
            for key, row in rows.items()
            if key != "(unattributed)"
        }
        assert python == sql, label
        assert json.loads(rows["(unattributed)"]["stretches_json"]) == [{"start_mile": s, "end_mile": e} for s, e in unattributed]


# --- the two file-level differences ---------------------------------------------------


def test_trail_miles_parity_holds_trails_sha256_to_its_own_trails_geojson(tmp_path):
    """parity.py swaps trails_sha256 for whether it names the trails.geojson beside it (DELIBERATE)."""
    import parity

    (tmp_path / "trails.geojson").write_bytes(b'{"type":"FeatureCollection"}')
    digest = hashlib.sha256(b'{"type":"FeatureCollection"}').hexdigest()
    shaped = parity._trail_miles_records({"format": 1, "trails_sha256": digest, "miles": {}}, tmp_path / "trail_miles.json")
    swapped = {"trails_sha256"} - set(shaped)
    assert swapped == {key for source, key in DELIBERATE if source == "parity.py trail_miles"}
    assert shaped["trails_sha256_names_its_trails_geojson"] is True


def test_club_sections_dates_no_layer_until_the_extract_lands_the_dates():
    writer = (DBT / "models" / "publish" / "pub_club_sections.sql").read_text()
    written_empty = "json('{}') as source_edited" in writer
    assert written_empty == (("pub_club_sections", "source_edited") in DELIBERATE)
