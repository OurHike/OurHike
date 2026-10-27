"""The whole job from raw files to its two outputs, on invented sites."""

from __future__ import annotations

import json

import pytest
from conftest import FEET_PER_DEG, csi_row, point, square, write_raw

from steward_analysis import build, rules


def invented_layer() -> tuple[list[dict], list[dict], list[dict]]:
    """Eight invented sites in two clubs, two parking points and two land units."""
    rows = [
        # A complex of three user-created sites around a shelter, close to water: crew-sized.
        csi_row(1, north_ft=0, Proximity_Water_ft=60, Size_Indicator=0, Size_ft2=1800, CSI_Score=None),
        csi_row(2, north_ft=120, Size_Indicator=1, Size_ft2=900, CSI_Score=None),
        csi_row(3, north_ft=240, Site_Type=rules.SHELTER, Expansion_Potential_Indicator=0, Size_Indicator=0, CSI_Score=None),
        # Alone, small and flat, with a poor score: a one-person job.
        csi_row(
            4,
            north_ft=5000,
            Size_ft2=300,
            Expansion_Potential_Indicator=0,
            Size_Indicator=1,
            Proximity_Water_Social_Indicator=0,
            Proximity_AT_Indicator=0,
            Proximity_Water_Ecological_Indicator=1,
            CSI_Score=None,
        ),
        # A good site: the "your club may want to adopt it" note.
        csi_row(
            5,
            north_ft=9000,
            Expansion_Potential_Indicator=3,
            Size_Indicator=3,
            Side_Hill_Footprint_Indicator=1,
            Side_Hill_Buffer_Indicator=1,
            CSI_Score=None,
        ),
        # Already recovering.
        csi_row(6, north_ft=12000, Inventory_Status="Closed/Recovering", CSI_Score=None),
        # Another club, and a blank site type.
        csi_row(7, north_ft=40000, Trail_Club="Second Example Club", Site_Type=" ", CSI_Score=None),
        csi_row(8, north_ft=40500, Trail_Club="Second Example Club", CSI_Score=None),
    ]
    for row in rows:
        row["CSI_Score"] = rules.csi_from_indicators(row)
    parking = [point(-1000, 0, Name="Example Gap lot"), point(41000, 0, Name="Example Notch lot")]
    padus = [
        square(0, 0, 20000, OBJECTID=1, Mang_Name="USFS", Des_Tp="NF", Unit_Nm="Example National Forest", State_Nm="XX"),
        square(40000, 0, 2000, OBJECTID=2, Mang_Name="SFW", Des_Tp="SRMA", Unit_Nm="Example Game Land", State_Nm="XX"),
    ]
    return rows, parking, padus


@pytest.fixture
def built(tmp_path):
    rows, parking, padus = invented_layer()
    # A trail running north-south 120 ft west of every invented site, matching csi_row's
    # default Proximity_AT_ft, so the job's distance and ATC's agree.
    trail = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-120 / FEET_PER_DEG, -0.01], [-120 / FEET_PER_DEG, 0.2]]},
        "properties": {},
    }
    write_raw(tmp_path / "raw", rows, parking, padus, centerline=[trail])
    summary = build.run(tmp_path)
    sites = json.loads((tmp_path / "out" / "sites.json").read_text())
    return rows, json.loads((tmp_path / "out" / "summary.json").read_text()), summary, sites


def walk(value, path=()):
    """Every (key path, leaf value) in a JSON document."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk(v, (*path, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, (*path, i))
    else:
        yield path, value


def test_the_summary_carries_no_location_of_any_site(built):
    """summary.json is the Analysis screen's whole input (PLAN.md §2g). It stays counts only, so that
    screen never needs the 3.7 MB of locations, and so a chart can never leak one place by accident."""
    rows, summary, _, _ = built
    forbidden_keys = {"lat", "lon", "latitude", "longitude", "mile", "coordinates", "rims_id", "global_id", "name", "location"}
    identifying = {str(r[f]) for r in rows for f in ("RIMS_ID", "GlobalID", "Location")}
    coordinates = {round(r[f], 5) for r in rows for f in ("Latitude", "Longitude")} - {0.0}
    for path, value in walk(summary):
        assert not ({str(k).lower() for k in path} & forbidden_keys), path
        assert str(value) not in identifying, path
        if isinstance(value, float):
            assert round(value, 5) not in coordinates, path


def test_sites_json_holds_every_site_with_its_location_grouped_by_club_then_need(built):
    _, _, _, sites = built
    assert len(sites) == 8
    assert all(s["lat"] is not None and s["lon"] is not None and s["mile"] for s in sites)
    clubs = [s["club"] for s in sites]
    assert clubs == sorted(clubs)
    first_club = [s["need"] for s in sites if s["club"] == "Example Trail Club"]
    assert len(first_club) == 6 and first_club == sorted(first_club, reverse=True)


def test_each_site_s_need_is_its_need_parts_under_the_default_weights(built):
    # The web app re-ranks under a club's weights from need_parts alone (#1906), so
    # under the defaults the parts must give back exactly the need the job wrote.
    _, _, _, sites = built
    scored = [s for s in sites if s["need_parts"] is not None]
    assert scored
    for s in scored:
        assert list(s["need_parts"]) == list(rules.WEIGHT_NAMES)
        assert rules.need_from_parts(s["need_parts"]) == s["need"], s["rims_id"]


def test_sites_json_never_carries_atcs_photo_links(built):
    _, _, _, sites = built
    assert not any("photo" in str(k).lower() for s in sites for k in s)


def test_actions_crews_and_complexes_come_out_as_the_rules_say(built):
    _, _, _, sites = built
    by_id = {s["rims_id"]: s for s in sites}
    assert {by_id[f"rims-000{n}"]["complex_id"] for n in (1, 2, 3)} == {"cx-rims-000"}
    assert by_id["rims-0001"]["complex_size"] == 3
    assert (by_id["rims-0001"]["action"], by_id["rims-0001"]["crew"]) == (rules.CLOSE_RESTORE, rules.CREW)
    assert (by_id["rims-0003"]["action"], by_id["rims-0003"]["crew"]) == (rules.HARDEN, rules.CREW)
    assert (by_id["rims-0004"]["action"], by_id["rims-0004"]["crew"]) == (rules.CLOSE_RESTORE, rules.ONE_PERSON)
    assert by_id["rims-0005"]["action"] == rules.ADOPT_NOTE and by_id["rims-0005"]["tier"] is None
    assert (by_id["rims-0006"]["action"], by_id["rims-0006"]["need"]) == (rules.MONITOR_RECOVERY, 0)
    assert by_id["rims-0007"]["action"] == rules.UNKNOWN


def test_each_site_says_where_to_leave_the_trail_and_which_way_to_walk(built):
    _, _, _, sites = built
    first = next(s for s in sites if s["rims_id"] == "rims-0001")
    assert first["from_trail"]["toward"] == "E"
    assert first["from_trail"]["ft"] == pytest.approx(120, abs=2)


def test_a_raw_directory_without_the_centerline_still_scores_with_no_bearing(tmp_path):
    rows, parking, padus = invented_layer()
    write_raw(tmp_path / "raw", rows, parking, padus)
    build.run(tmp_path)
    sites = json.loads((tmp_path / "out" / "sites.json").read_text())
    assert all(s["from_trail"] is None for s in sites)


def test_nearest_parking_and_land_unit_are_named_on_each_site(built):
    _, _, _, sites = built
    first = next(s for s in sites if s["rims_id"] == "rims-0001")
    assert first["nearest_parking"]["name"] == "Example Gap lot"
    assert first["nearest_parking"]["mi"] == pytest.approx(1000 / 5280, abs=0.01)
    assert first["land_unit"]["name"] == "Example National Forest"
    assert first["camping"] == {"regime": "dispersed_allowed?", "source": "guess"}


def test_the_summary_counts_and_checks_the_csi_formula(built):
    _, summary, returned, _ = built
    assert returned["priority_by_crew"] == summary["priority_by_crew"]
    assert summary["source"]["sites"] == 8
    assert summary["source"]["data_last_edited"] == "2026-08-20"
    assert summary["csi_formula"] == {"reproduces": 8, "of": 8, "incomplete_rows": 0}
    assert summary["complexes"]["with_2_plus"] == 1
    assert summary["camping_rules"]["reviewed_units"] == 0
    assert (
        sum(row["total"] for row in summary["priority_by_crew"])
        == summary["actions"][rules.CLOSE_RESTORE] + summary["actions"][rules.HARDEN]
    )
    assert [c["club"] for c in summary["clubs"]][0] == "Example Trail Club"


def test_a_published_score_the_formula_no_longer_reproduces_is_counted_not_hidden(tmp_path):
    rows, parking, padus = invented_layer()
    rows[0]["CSI_Score"] += 1
    write_raw(tmp_path / "raw", rows, parking, padus)
    assert build.run(tmp_path)["csi_formula"]["reproduces"] == 7


def test_a_guessed_camping_regime_never_moves_a_sites_need_and_a_reviewed_rule_does():
    rows, parking, padus = invented_layer()
    guessed = build.score(rows, {"features": parking}, {"features": padus})
    reviewed = build.score(rows, {"features": parking}, {"features": padus}, camping_rules={"Example Game Land": True})
    site8 = lambda df: int(df.loc[df["RIMS_ID"] == "rims-0008", "need"].iloc[0])  # noqa: E731
    assert guessed.loc[guessed["RIMS_ID"] == "rims-0008", "regime_guess"].iloc[0] == "restricted?"
    assert site8(reviewed) == site8(guessed) + rules.DEFAULT_WEIGHTS.restricted


def test_a_row_missing_a_field_the_rules_read_is_unknown_and_counted(tmp_path):
    rows, parking, padus = invented_layer()
    rows[3]["Size_ft2"] = None
    write_raw(tmp_path / "raw", rows, parking, padus)
    summary = build.run(tmp_path)
    assert summary["csi_formula"]["incomplete_rows"] == 1
    assert summary["actions"][rules.UNKNOWN] == 2


def test_a_site_without_coordinates_is_skipped_and_counted(tmp_path):
    rows, parking, padus = invented_layer()
    rows[4]["Latitude"] = None
    write_raw(tmp_path / "raw", rows, parking, padus)
    summary = build.run(tmp_path)
    assert (summary["source"]["sites"], summary["source"]["skipped_no_location"]) == (7, 1)


def test_a_layer_that_lost_a_field_is_refused_before_scoring():
    rows, _, _ = invented_layer()
    del rows[0]["Proximity_Water_ft"]
    with pytest.raises(build.SchemaError, match="Proximity_Water_ft"):
        build.check_schema(rows)


def test_directions_are_withheld_where_the_centerline_disagrees_with_atcs_own_distance(tmp_path):
    """The Georgia case: ATC says the site is beside the trail, and the centerline has none for miles."""
    rows, parking, padus = invented_layer()
    for row in rows:
        row["Proximity_AT_ft"] = 20.0
    far_trail = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-20000 / FEET_PER_DEG, -0.01], [-20000 / FEET_PER_DEG, 0.2]]},
        "properties": {},
    }
    write_raw(tmp_path / "raw", rows, parking, padus, centerline=[far_trail])
    summary = build.run(tmp_path)
    sites = json.loads((tmp_path / "out" / "sites.json").read_text())
    assert all(s["from_trail"] is None for s in sites)
    assert summary["from_trail"]["withheld_disagreeing_with_atc"] == 8
