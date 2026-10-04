"""int_closures__club_notices' unit test reads the status seed the build reads (decision 53, phase C).

The unit test mocks seeds/notice_status_values.csv; this holds the mock to the
file row for row, so the test cannot pass on a vocabulary the build does not
use. It also holds the two phase C cases the brief named to the seed: USFS
R06's 'Active' and CDPR's 'Full Closure' are both read as closing, which is
what makes "never closed now once its own end has passed" a rule about them
rather than about rows that could never close anything.
"""

import csv
from pathlib import Path

import yaml

DBT = Path(__file__).resolve().parent.parent / "dbt"
CLOSURES = DBT / "models" / "intermediate" / "closures" / "_closures__intermediate.yml"
TEST = "int_closures__club_notices_holds_back_what_its_own_dates_and_status_say_is_not_current"


def _unit_test() -> dict:
    return {test["name"]: test for test in yaml.safe_load(CLOSURES.read_text())["unit_tests"]}[TEST]


def _seed(name: str) -> list[dict]:
    with (DBT / "seeds" / f"{name}.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_the_unit_tests_mocked_status_seed_is_the_seed_file():
    (given,) = [g for g in _unit_test()["given"] if g["input"] == "ref('notice_status_values')"]
    assert given["rows"] == _seed("notice_status_values")


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


def test_the_unit_test_holds_both_named_cases_back_once_their_end_has_passed():
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
        assert out["obstructs_trail"] is None and out["held_because"].startswith("its own end date"), row
