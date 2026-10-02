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
"""

import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, MultiLineString, Point
from shapely.strtree import STRtree

import export_club_sections
import export_elevation
import export_nearby_trails
import export_spurs
import export_trails
from lib import club_sections as lib_club_sections
from lib import corridor
from lib import spurs as lib_spurs
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
