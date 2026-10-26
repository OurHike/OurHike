from dataclasses import replace

import pytest

from steward_analysis import rules
from steward_analysis.rules import SiteFacts

#: A mid-band user-created site that triggers nothing: each test changes one thing.
QUIET = SiteFacts(
    site_type=rules.USER_CREATED,
    inventory_status="Established",
    csi=18,
    size_ft2=400,
    water_ft=450,
    trail_ft=120,
    slope_footprint_pct=6,
    complex_size=1,
)


def test_csi_weights_sum_the_eight_indicators_to_ATCs_published_maximum_of_30():
    best = {field: (1 if "Side_Hill" in field else 3) for field in rules.CSI_WEIGHTS}
    assert rules.csi_from_indicators(best) == rules.CSI_MAX == 30


def test_csi_from_indicators_weights_size_and_expansion_twice_and_each_side_hill_flag_three_times():
    indicators = dict.fromkeys(rules.CSI_WEIGHTS, 0) | {
        "Size_Indicator": 1,
        "Expansion_Potential_Indicator": 1,
        "Side_Hill_Footprint_Indicator": 1,
        "Proximity_AT_Indicator": 1,
    }
    assert rules.csi_from_indicators(indicators) == 2 + 2 + 3 + 1


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"inventory_status": "Closed/Recovering", "csi": 3}, rules.MONITOR_RECOVERY),
        ({"inventory_status": "Site Absent/Recovered"}, rules.MONITOR_RECOVERY),
        ({"site_type": rules.SHELTER, "csi": 12}, rules.HARDEN),
        ({"site_type": rules.CLUB_CAMPSITE, "csi": 13}, rules.MONITOR),
        ({"site_type": rules.SHELTER, "csi": 22}, rules.OK),
        ({"site_type": rules.SHELTER, "csi": 20, "water_ft": 10}, rules.MONITOR),
        ({"csi": 12}, rules.CLOSE_RESTORE),
        ({"csi": 13}, rules.MONITOR),
        ({"csi": 25, "water_ft": 99}, rules.CLOSE_RESTORE),
        ({"csi": 20, "water_ft": 100}, rules.MONITOR),
        ({"csi": 22}, rules.ADOPT_NOTE),
        ({"site_type": ""}, rules.UNKNOWN),
    ],
)
def test_action(changes, expected):
    assert rules.action(replace(QUIET, **changes)) == expected


def test_need_is_the_csi_deficit_alone_for_a_site_that_triggers_nothing_else():
    assert rules.need(replace(QUIET, csi=30)) == 0
    assert rules.need(replace(QUIET, csi=3)) == 60
    assert rules.need(replace(QUIET, csi=18)) == round(60 * 12 / 27)


@pytest.mark.parametrize(
    ("changes", "points"),
    [
        ({"water_ft": 99}, 12),
        ({"water_ft": 150}, 6),
        ({"water_ft": 200}, 0),
        ({"trail_ft": 49}, 6),
        ({"trail_ft": 50}, 0),
        ({"complex_size": 4}, 8),
        ({"complex_size": 2}, 4),
        ({"camping_restricted": True}, 10),
    ],
)
def test_need_adds_points_for_water_trail_cluster_and_reviewed_restricted_camping(changes, points):
    base = replace(QUIET, csi=30)
    assert rules.need(replace(base, **changes)) == points


def test_restricted_camping_adds_nothing_to_an_official_site():
    assert rules.need(replace(QUIET, csi=30, site_type=rules.SHELTER, camping_restricted=True)) == 0


def test_need_is_zero_for_a_site_already_recovering_and_never_above_100():
    assert rules.need(replace(QUIET, csi=3, inventory_status="Closed/Recovering")) == 0
    worst = replace(QUIET, csi=3, water_ft=1, trail_ft=1, complex_size=9, camping_restricted=True)
    assert rules.need(worst, rules.Weights(deficit=90)) == 100


def test_a_club_can_change_the_weights_and_the_need_follows():
    near_water = replace(QUIET, csi=30, water_ft=50)
    assert rules.need(near_water) == 12
    assert rules.need(near_water, rules.Weights(water=30)) == 30


@pytest.mark.parametrize(
    ("need", "action", "expected"),
    [
        (60, rules.CLOSE_RESTORE, "P1"),
        (59, rules.CLOSE_RESTORE, "P2"),
        (50, rules.HARDEN, "P2"),
        (49, rules.HARDEN, "P3"),
        (90, rules.MONITOR, None),
        (90, rules.ADOPT_NOTE, None),
    ],
)
def test_tier(need, action, expected):
    assert rules.tier(need, action) == expected


@pytest.mark.parametrize(
    ("changes", "action", "expected"),
    [
        ({}, rules.HARDEN, rules.CREW),
        ({"size_ft2": 1501}, rules.CLOSE_RESTORE, rules.CREW),
        ({"complex_size": 4}, rules.CLOSE_RESTORE, rules.CREW),
        ({"size_ft2": 1500}, rules.CLOSE_RESTORE, rules.TEAM),
        ({"size_ft2": 501}, rules.CLOSE_RESTORE, rules.TEAM),
        ({"complex_size": 2}, rules.CLOSE_RESTORE, rules.TEAM),
        ({"slope_footprint_pct": 15}, rules.CLOSE_RESTORE, rules.TEAM),
        ({"size_ft2": 500}, rules.CLOSE_RESTORE, rules.ONE_PERSON),
        ({"size_ft2": 100, "water_ft": 5}, rules.CLOSE_RESTORE, rules.ONE_PERSON),
        ({}, rules.MONITOR, None),
    ],
)
def test_crew(changes, action, expected):
    assert rules.crew(replace(QUIET, **changes), action) == expected


@pytest.mark.parametrize(
    ("manager", "designation", "unit", "expected"),
    [
        ("NPS", "NP", "Great Smoky Mountains National Park", "designated_only?"),
        ("NPS", "NP", "Shenandoah National Park", "permit_or_designated?"),
        ("USFS", "NF", "Jefferson National Forest", "dispersed_allowed?"),
        ("SFW", "SRMA", "State Game Land 211", "restricted?"),
        ("SDNR", "SP", "South Mountain State Park", "designated_only?"),
        ("NPS", "NT", "Appalachian National Scenic Trail", "unknown"),
        (None, None, None, "unknown"),
    ],
)
def test_regime_guess_marks_every_guess_with_a_question_mark(manager, designation, unit, expected):
    assert rules.regime_guess(manager, designation, unit) == expected
