"""parity.py's v2 families: a v2 phone file decodes to exactly the values its v1 carries (decision 44, stage 6 of #1793).

Elevation, miles and coordinates are safety fields (pipeline/ELT.md, "The
eleven marts"), so these hold the Python decoders, which CI's parity step
runs against the dbt writers' files, to the cases the formats exist for: a
DEM gap that stays unknown and never becomes 0, a chain that steps
backwards, a coordinate whose seventh decimal is a half, and a v2 file one
millionth of a degree off v1, which must fail rather than pass as rounding.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

import parity

PIPELINE = Path(__file__).resolve().parent.parent
PUBLISH = PIPELINE / "dbt" / "models" / "publish"
WORKFLOW = PIPELINE.parent / ".github" / "workflows" / "pipeline-tests.yml"


# --- decode_elevation_profile_v2 --------------------------------------------


def test_decode_elevation_profile_v2_sums_each_column_from_its_first_value():
    document = {"format": 2, "d_milli_mi": [0, 16, 15], "e_deci_ft": [7064, 45, -9], "part_start": [0]}
    assert parity.decode_elevation_profile_v2(document) == [
        {"distance_mi": 0.0, "elevation_ft": 706.4, "part_start": True},
        {"distance_mi": 0.016, "elevation_ft": 710.9},
        {"distance_mi": 0.031, "elevation_ft": 710.0},
    ]


def test_decode_elevation_profile_v2_keeps_a_dem_gap_null_and_steps_past_it_from_the_last_known_height():
    """A null is no DEM answer, never 0 ft: the step after a gap is from the last elevation that exists."""
    document = {"format": 2, "d_milli_mi": [100, 16, 16, 16], "e_deci_ft": [None, 7000, None, 25], "part_start": [0, 2]}
    assert parity.decode_elevation_profile_v2(document) == [
        {"distance_mi": 0.1, "elevation_ft": None, "part_start": True},
        {"distance_mi": 0.116, "elevation_ft": 700.0},
        {"distance_mi": 0.132, "elevation_ft": None, "part_start": True},
        {"distance_mi": 0.148, "elevation_ft": 702.5},
    ]


def test_decode_elevation_profile_v2_gives_the_double_json_loads_gives_v1s_text():
    """2197.989 is not exact in binary; a thousandth-count over 1,000 must land on the same double as the text."""
    (record,) = parity.decode_elevation_profile_v2({"format": 2, "d_milli_mi": [2197989], "e_deci_ft": [53001], "part_start": []})
    assert record == json.loads('{"distance_mi": 2197.989, "elevation_ft": 5300.1}')
    assert json.dumps(record) == '{"distance_mi": 2197.989, "elevation_ft": 5300.1}'


def test_decode_elevation_profile_v2_decodes_an_empty_profile_to_no_samples():
    assert parity.decode_elevation_profile_v2({"format": 2, "d_milli_mi": [], "e_deci_ft": [], "part_start": []}) == []


@pytest.mark.parametrize(
    "document",
    [
        [{"distance_mi": 0.0, "elevation_ft": 1.0}],
        {"format": 1, "d_milli_mi": [], "e_deci_ft": [], "part_start": []},
        {"format": 2, "d_milli_mi": [0, 1], "e_deci_ft": [0], "part_start": []},
        {"format": 2, "d_milli_mi": [0], "e_deci_ft": [0], "part_start": [1]},
        {"format": 2, "d_milli_mi": [0.5], "e_deci_ft": [0], "part_start": []},
        {"format": 2, "d_milli_mi": [0], "e_deci_ft": [0]},
    ],
    ids=["a_v1_array", "format_1", "columns_of_two_lengths", "part_start_past_the_end", "a_fraction", "no_part_start"],
)
def test_decode_elevation_profile_v2_refuses_what_is_not_a_v2_profile(document):
    with pytest.raises(ValueError):
        parity.decode_elevation_profile_v2(document)


# --- decode_trail_miles_v2 ---------------------------------------------------


def test_decode_trail_miles_v2_gives_v1s_document_with_negative_steps_kept():
    """A chain that runs backwards for a step (monotonic_breaks) keeps the step: the phone splits a piece there."""
    document = {
        "format": 2,
        "trails_sha256": "a" * 64,
        "axis": "export_elevation.calibrated_trail_axis",
        "decimals": 3,
        "feature_count": 2,
        "vertex_count": 5,
        "milli_mile_deltas": {"centerline:chain:0": [0, 348, -2], "centerline:chain:1": [500, 1]},
    }
    assert parity.decode_trail_miles_v2(document) == {
        "format": 1,
        "trails_sha256": "a" * 64,
        "axis": "export_elevation.calibrated_trail_axis",
        "decimals": 3,
        "feature_count": 2,
        "vertex_count": 5,
        "miles": {"centerline:chain:0": [0.0, 0.348, 0.346], "centerline:chain:1": [0.5, 0.501]},
    }


@pytest.mark.parametrize(
    "document",
    [
        {"format": 1, "miles": {}},
        {"format": 2, "miles": {}},
        {"format": 2, "milli_mile_deltas": {"centerline:chain:0": [0.348]}},
    ],
    ids=["format_1", "v1s_miles_under_format_2", "a_fraction"],
)
def test_decode_trail_miles_v2_refuses_what_is_not_a_v2_file(document):
    with pytest.raises(ValueError):
        parity.decode_trail_miles_v2(document)


# --- poi_v1_at_six_decimals ---------------------------------------------------


def _feature(lat, lon, **properties):
    return {
        "type": "Feature",
        "properties": {"id": "x:1", "lat": lat, "lon": lon, **properties},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def test_poi_v1_at_six_decimals_holds_the_position_once_cut_by_pythons_round():
    """41.0078125 is exact in binary and its seventh decimal is a half: round() takes it to even, 41.007812."""
    cut = parity.poi_v1_at_six_decimals({"type": "FeatureCollection", "features": [_feature(41.0078125, -73.98999999999999)]})
    (feature,) = cut["features"]
    assert feature["properties"] == {"id": "x:1"}
    assert feature["geometry"] == {"type": "Point", "coordinates": [-73.99, 41.007812]}


def test_poi_v1_at_six_decimals_cuts_the_properties_a_v1_phone_reads_not_the_geometry():
    """poi_<type>.geojson's geometry is GDAL's printing and can differ from its properties; readPois reads the properties."""
    feature = _feature(41.1234565000001, -74.0)
    feature["geometry"]["coordinates"] = [-74.0, 41.1234564999999]
    (cut,) = parity.poi_v1_at_six_decimals({"features": [feature]})["features"]
    assert cut["geometry"]["coordinates"] == [-74.0, 41.123457]


# --- the families, end to end ------------------------------------------------


def _run(tmp_path, family, v1_name, v1, v2_name, v2):
    (tmp_path / v1_name).write_text(json.dumps(v1))
    (tmp_path / v2_name).write_text(json.dumps(v2))
    return parity.main([family, "--new", str(tmp_path / v2_name)])


V1_POIS = {"type": "FeatureCollection", "name": "water", "features": [_feature(41.1000004, -73.89, name="Spring")]}


def _v2_pois(coordinates):
    return {
        "type": "FeatureCollection",
        "name": "water",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "x:1", "name": "Spring"},
                "geometry": {"type": "Point", "coordinates": coordinates},
            }
        ],
    }


def test_poi_water_v2_agrees_with_v1_at_six_decimals(tmp_path, capsys):
    assert _run(tmp_path, "poi_water_v2", "poi_water.geojson", V1_POIS, "poi_water_v2.geojson", _v2_pois([-73.89, 41.1])) == 0
    assert "no differences across 1 features" in capsys.readouterr().out


def test_poi_water_v2_one_millionth_of_a_degree_off_v1_is_a_difference_not_rounding(tmp_path, capsys):
    """A coordinate that moves is a location error: 1e-6 degrees, about 0.11 m, still fails the line."""
    assert (
        _run(tmp_path, "poi_water_v2", "poi_water.geojson", V1_POIS, "poi_water_v2.geojson", _v2_pois([-73.89, 41.100001])) == 1
    )
    assert "properties.id x:1" in capsys.readouterr().out


def test_poi_water_v2_with_lat_and_lon_still_in_its_properties_is_a_difference(tmp_path):
    v2 = _v2_pois([-73.89, 41.1])
    v2["features"][0]["properties"].update(lat=41.1, lon=-73.89)
    assert _run(tmp_path, "poi_water_v2", "poi_water.geojson", V1_POIS, "poi_water_v2.geojson", v2) == 1


def test_elevation_v2_a_dem_gap_written_as_zero_is_a_difference(tmp_path, capsys):
    """Absent means no DEM coverage, never 0: a v2 that wrote the gap as a 0 step fails, it does not pass as equal."""
    v1 = [{"distance_mi": 0.0, "elevation_ft": 706.4, "part_start": True}, {"distance_mi": 0.016, "elevation_ft": None}]
    v2 = {"format": 2, "d_milli_mi": [0, 16], "e_deci_ft": [7064, 0], "part_start": [0]}
    assert _run(tmp_path, "elevation_v2", "elevation_profile.json", v1, "elevation_profile_v2.json", v2) == 1
    assert "distance_mi 0.016" in capsys.readouterr().out
    v2["e_deci_ft"][1] = None
    assert _run(tmp_path, "elevation_v2", "elevation_profile.json", v1, "elevation_profile_v2.json", v2) == 0


def test_trail_miles_v2_a_mile_one_thousandth_off_is_a_difference(tmp_path):
    (tmp_path / "trails.geojson").write_text("{}")
    sha = __import__("hashlib").sha256(b"{}").hexdigest()
    header = {"trails_sha256": sha, "axis": "a", "decimals": 3, "feature_count": 1, "vertex_count": 2}
    v1 = {"format": 1, **header, "miles": {"centerline:chain:0": [0.0, 0.348]}}
    good = {"format": 2, **header, "milli_mile_deltas": {"centerline:chain:0": [0, 348]}}
    off = {"format": 2, **header, "milli_mile_deltas": {"centerline:chain:0": [0, 349]}}
    assert _run(tmp_path, "trail_miles_v2", "trail_miles.json", v1, "trail_miles_v2.json", good) == 0
    assert _run(tmp_path, "trail_miles_v2", "trail_miles.json", v1, "trail_miles_v2.json", off) == 1


# --- every v2 file has its parity line ---------------------------------------


def _v2_exposures() -> dict[str, dict]:
    found = {}
    for path in sorted(PUBLISH.glob("*.yml")):
        for exposure in yaml.safe_load(path.read_text()).get("exposures") or []:
            keys = exposure["config"]["meta"]["r2_keys"]
            if any(key.startswith("v2/") for key in keys):
                found[exposure["name"]] = exposure
    return found


def test_every_v2_phone_file_is_held_to_its_v1_by_a_parity_family_and_a_ci_line():
    """A v2 writer nobody decodes against v1 could ship a moved coordinate or a zeroed DEM gap unseen."""
    workflow = WORKFLOW.read_text()
    exposures = _v2_exposures()
    assert len(exposures) == 11, sorted(exposures)
    for name, exposure in exposures.items():
        (key,) = exposure["config"]["meta"]["r2_keys"]
        v1_name = key.removeprefix("v2/")
        family_name = v1_name.split(".")[0].removesuffix("_profile") + "_v2"
        family = parity.FAMILIES[family_name]
        assert family.v1_beside == v1_name, name
        writer = next(ref for ref in exposure["depends_on"] if ref.startswith("ref('pub_"))
        location = re.search(r"location='([^']+)'", (PUBLISH / f"{writer[5:-2]}.sql").read_text()).group(1)
        assert f"parity.py {family_name} --new data/processed/dbt/{location}" in workflow, family_name
