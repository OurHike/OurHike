"""int_closures__club_notices' unit test reads the status seeds the build reads (decision 53, phase C).

The unit test mocks seeds/notice_status_values.csv and seeds/notice_category_values.csv; this holds each mock to
its file row for row, so the test cannot pass on a vocabulary the build does not use. It also holds the two phase C
cases the brief named to the seed: USFS R06's 'Active' and CDPR's 'Full Closure' are both read as closing, which is
what makes "never closed now once its own end has passed" a rule about them rather than about rows that could never
close anything. And since the maintainer's frame A (poll of 2026-10-10), such a notice is kept, not held back: the
phone greys it from conditions/notices.json's `current_until`.

And it holds the maintainer's answers of 2026-10-11 on how wave 6's statuses read (pages 01 and 02 of that review)
to the seeds, where a later edit would otherwise move one without a word: Missouri's Archived alone is not current
(P1), Michigan's '-1' is nothing for a hiker on both its layers (P4), a closed Florida park closes its trails (P5),
the Great Allegheny Passage's Hidden and Cleared are both not current (P6), and NETT's damaged bridges close the
trail with no status field to read (P11).
"""

import csv
from pathlib import Path

import yaml

DBT = Path(__file__).resolve().parent.parent / "dbt"
CLOSURES = DBT / "models" / "intermediate" / "closures" / "_closures__intermediate.yml"
TEST = "int_closures__club_notices_keeps_an_ended_notice_without_closing_and_holds_back_what_its_status_says_is_not_current"


def _unit_test() -> dict:
    return {test["name"]: test for test in yaml.safe_load(CLOSURES.read_text())["unit_tests"]}[TEST]


def _seed(name: str) -> list[dict]:
    with (DBT / "seeds" / f"{name}.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def _readings(name: str, value_column: str) -> dict[tuple[str, str], str]:
    return {(row["source_key"], row[value_column]): row["reads_as"] for row in _seed(name)}


def test_the_unit_tests_mocked_status_seed_is_the_seed_file():
    (given,) = [g for g in _unit_test()["given"] if g["input"] == "ref('notice_status_values')"]
    assert given["rows"] == _seed("notice_status_values")


def test_the_unit_tests_mocked_category_seed_is_the_seed_file():
    (given,) = [g for g in _unit_test()["given"] if g["input"] == "ref('notice_category_values')"]
    assert given["rows"] == _seed("notice_category_values")


def test_the_unit_tests_mocked_hazard_seed_is_the_seed_file():
    """Decision 67's hazard rule (rule 6) is tested on the categories the build reads."""
    (given,) = [g for g in _unit_test()["given"] if g["input"] == "ref('notice_hazard_areas')"]
    assert given["rows"] == _seed("notice_hazard_areas")


def test_no_hazard_seed_row_lists_a_category_that_says_the_hazard_is_absent():
    """A 'No hunting' parcel or a safety zone drawn as a hunting area would tell a hiker the opposite of the layer."""
    for row in _seed("notice_hazard_areas"):
        value = row["category_value"].lower()
        assert not value.startswith("no ") and "safety zone" not in value and value != "closed", row


def test_the_two_named_status_cases_close_in_the_seed():
    closing = {
        (row["source_key"], row["status_value"]) for row in _seed("notice_status_values") if row["reads_as"] == "closes_trail"
    }
    assert ("usfs_r06_fire_closure_lines", "Active") in closing
    assert ("cdpr_park_unit_status", "Full Closure") in closing


def test_the_unit_test_keeps_both_named_cases_once_their_end_has_passed_and_never_reads_them_as_closed():
    """Frame A keeps them (held_because null) and rule 2 still refuses to read them as closing the trail."""
    test = _unit_test()
    (given,) = [g for g in test["given"] if g["input"] == "ref('int_closures__club_notices_unioned')"]
    expected = {row["notice_id"]: row for row in test["expect"]["rows"]}
    ended = [
        row
        for row in given["rows"]
        if row["source_key"] in ("usfs_r06_fire_closure_lines", "cdpr_park_unit_status")
        and row["ends_at"]
        and row["ends_at"] < "2026"
    ]
    assert {row["source_key"] for row in ended} == {"usfs_r06_fire_closure_lines", "cdpr_park_unit_status"}
    for row in ended:
        out = expected[f"{row['source_key']}:{row['source_id']}"]
        assert out["obstructs_trail"] is None and out["held_because"] is None, row


def test_missouris_archived_is_its_only_status_read_as_not_current():
    """P1: "ONLY 'Archived' reads as not current; a blank STATUS shows as current" (not the recommendation)."""
    readings = {
        value: reads
        for (key, value), reads in _readings("notice_status_values", "status_value").items()
        if key == "mo_state_parks_trail_advisories"
    }
    assert {value for value, reads in readings.items() if reads == "not_current"} == {"Archived"}
    assert "" not in readings and "Caution" not in readings
    assert readings.get("Closed") == "closes_trail"


def test_michigans_unspecified_foot_travel_status_is_nothing_for_a_hiker_on_both_layers():
    """P4: '-1', the domain's 'Unspecified', on rows that close an ORV or snowmobile use, shows nothing."""
    readings = _readings("notice_status_values", "status_value")
    for key in ("mi_dnr_trail_temporary_closures", "mi_dnr_trail_temporary_reroutes"):
        assert readings[(key, "-1")] == "not_current", key
    closing = {
        value for (key, value), reads in readings.items() if key == "mi_dnr_trail_temporary_closures" and reads == "closes_trail"
    }
    assert len(closing) == 6 and all(value.startswith("Temporarily Closed") for value in closing), closing


def test_every_closed_value_of_a_florida_parks_day_use_status_closes_and_no_campground_value_does():
    """P5, frame A: a closed park's trails close with it until its own status reopens it; the campground layer was
    not asked, and a closed campground is not a closed trail."""
    readings = _readings("notice_status_values", "status_value")
    day_use = {value: reads for (key, value), reads in readings.items() if key == "fl_state_parks_day_use_status"}
    assert day_use.pop("Open") == "not_current"
    assert len(day_use) == 8 and all(value.startswith("Closed-") and reads == "closes_trail" for value, reads in day_use.items())
    assert not [
        value for (key, value), reads in readings.items() if key == "fl_state_parks_campground_status" and reads == "closes_trail"
    ]


def test_the_gap_alerts_hidden_and_cleared_are_both_not_current():
    """P6: Hidden (its visibility, staged as the status) and Cleared (its own status, staged as the category)."""
    assert _readings("notice_status_values", "status_value")[("gap_trail_alerts", "Hidden")] == "not_current"
    assert _readings("notice_category_values", "category_value")[("gap_trail_alerts", "Cleared")] == "not_current"


def test_netts_damaged_bridges_close_the_trail_through_the_empty_value():
    """P11, frame A: drawn closed with its date. The layer has no status field, so every row reads the empty value."""
    assert _readings("notice_status_values", "status_value")[("nett_damaged_bridges", "")] == "closes_trail"
