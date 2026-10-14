"""A mostly unmeasured A.T. profile never replaces a good one (decision 194, the maintainer's poll of 2026-10-14).

pub_elevation_profile and pub_elevation_profile_v2 each carry an error-level test, declared in
models/publish/_publish__elevation.yml, that fails the writer when more than dbt_project.yml's var
elevation_profile_max_null_share (1%, @unvalidated) of the A.T.'s samples have no height. Held here without a
warehouse:

- both tests are on their writers, at error, under the names below, and neither writer is keep_last_file, so a
  failure is a failed writer and never "nothing to write this run";
- each test's own expression, run in DuckDB, passes a profile at the share and fails one just over it, passes an
  empty profile (int_elevation__final's both-sources rule writes `[]`, the phone's honest "no profile") and counts a
  record with no height at all as null;
- the share is 1% outside fixture mode, and fixture mode's build_marts.FIXTURE_PROFILE_MAX_NULL_SHARE lies between
  that 1% and the fixture profile's own null share, so the fixture build writes its deliberate gaps and a fixture
  profile that lost most of its heights would still fail.

What a failure does next is held where each half lives: build_marts.py removing the files dbt already wrote and
exiting PARTIAL_EXIT in tests/test_build_marts.py, and publish.py keeping the bucket's last copy in
tests/test_publish_dbt.py.
"""

import json
import re
from pathlib import Path

import duckdb
import pytest
import yaml

import build_marts
import export_elevation
import make_dbt_fixtures

DBT = Path(__file__).parent.parent / "dbt"
PUBLISH_YAML = DBT / "models" / "publish" / "_publish__elevation.yml"
VARIABLES = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]

#: Each profile writer's null-share test, by the name the YAML gives it: the name dbt's unique id and every failure
#: line in build_marts.py's and publish.py's logs carry.
CHECKS = {
    "pub_elevation_profile": "pub_elevation_profile_leaves_no_more_than_its_share_of_heights_null",
    "pub_elevation_profile_v2": "pub_elevation_profile_v2_leaves_no_more_than_its_share_of_heights_null",
}


def _check(model: str) -> dict:
    (node,) = [entry for entry in yaml.safe_load(PUBLISH_YAML.read_text())["models"] if entry["name"] == model]
    found = [
        test["dbt_utils.expression_is_true"]
        for test in node.get("data_tests") or []
        if isinstance(test, dict) and (test.get("dbt_utils.expression_is_true") or {}).get("name") == CHECKS[model]
    ]
    assert len(found) == 1, f"{model} declares its null-share test {CHECKS[model]} once"
    return found[0]


def _share_outside_fixtures() -> float:
    """The var's value when build_marts.py sets no variable: the default its env_var() names."""
    match = re.fullmatch(
        r"\{\{\s*env_var\('(\w+)',\s*'([0-9.]+)'\)\s*\}\}", str(VARIABLES["elevation_profile_max_null_share"]).strip()
    )
    assert match, VARIABLES["elevation_profile_max_null_share"]
    assert match.group(1) == build_marts.PROFILE_NULL_SHARE_VARIABLE
    return float(match.group(2))


def _passes(model: str, value, share: float) -> bool:
    """dbt_utils.expression_is_true over the writer's one row: it fails when the row does not satisfy the expression."""
    expression = re.sub(
        r"\{\{\s*var\('elevation_profile_max_null_share'\)\s*\}\}", repr(share), _check(model)["arguments"]["expression"]
    )
    assert "{{" not in expression and "{%" not in expression
    column, kind = ("profile_json", "varchar") if model == "pub_elevation_profile" else ("e_deci_ft", "integer[]")
    with duckdb.connect() as con:
        (failing,) = con.execute(
            f"select count(*) from (select cast(? as {kind}) as {column}) where not ({expression})", [value]
        ).fetchone()
    return failing == 0


def _profile(heights: list) -> str:
    """elevation_profile.json as pub_elevation_profile writes it: one record a sample, a null height written null."""
    return json.dumps([{"distance_mi": index / 40, "elevation_ft": height} for index, height in enumerate(heights)])


def test_each_profile_writer_carries_its_null_share_test_at_error():
    for model in CHECKS:
        assert _check(model)["config"]["severity"] == "error", model


@pytest.mark.parametrize("model", CHECKS)
def test_neither_profile_writer_keeps_its_last_file_on_an_empty_selection(model):
    """A keep_last_file writer that selects nothing writes nothing and succeeds; these select one row whatever the
    mart holds, so the only way either keeps the last good file is its test failing."""
    config = re.search(r"\{\{\s*config\((.*?)\)\s*\}\}", (DBT / "models" / "publish" / f"{model}.sql").read_text(), re.S)
    assert config and "when_empty" not in config.group(1)


def test_the_share_is_one_percent_outside_fixture_mode_and_fixture_modes_is_looser():
    assert _share_outside_fixtures() == 0.01
    assert float(build_marts.FIXTURE_PROFILE_MAX_NULL_SHARE) > _share_outside_fixtures()


@pytest.mark.parametrize(
    "heights, passes",
    [
        ([1000.5] * 200, True),
        ([None] * 2 + [1000.5] * 198, True),  # exactly 1%
        ([None] * 3 + [1000.5] * 197, False),  # 1.5%
        ([None] * 200, False),  # the DEM stopped answering
        ([], True),  # no A.T. row: the both-sources rule's empty profile
    ],
    ids=["none null", "one percent", "just over", "all null", "empty"],
)
def test_the_v1_check_fails_a_profile_more_than_one_percent_null(heights, passes):
    assert _passes("pub_elevation_profile", _profile(heights), _share_outside_fixtures()) is passes


def test_the_v1_check_counts_a_record_with_no_height_as_null():
    """A record the writer wrote without `elevation_ft` would be a sample nobody measured: absent is unknown."""
    records = json.loads(_profile([1000.5] * 200))
    for record in records[:3]:
        del record["elevation_ft"]
    assert _passes("pub_elevation_profile", json.dumps(records), _share_outside_fixtures()) is False


@pytest.mark.parametrize(
    "steps, passes",
    [
        ([10005] + [3] * 199, True),
        ([None, None, 10005] + [3] * 197, True),
        ([None, None, None, 10005] + [3] * 196, False),
        ([None] * 200, False),
        ([], True),
    ],
    ids=["none null", "one percent", "just over", "all null", "empty"],
)
def test_the_v2_check_fails_the_same_profiles(steps, passes):
    assert _passes("pub_elevation_profile_v2", steps, _share_outside_fixtures()) is passes


def test_the_fixture_share_lies_between_the_real_share_and_the_fixture_profiles_own(tmp_path):
    """build_profile on make_dbt_fixtures.py's files, the profile the fixture build writes (parity.py's elevation
    family holds the two equal): its gaps are over 1%, so fixture mode needs its own share, and under it."""
    raw = tmp_path / "raw"
    make_dbt_fixtures.write_fixtures(raw)
    index = tmp_path / "tile_index.json"
    index.write_text((raw / make_dbt_fixtures.ELEVATION_FIXTURE_INDEX).read_text())
    records, _ = export_elevation.build_profile(
        raw / "centerline.geojson", raw / "half_mile_points_from_springer.geojson", index, export_elevation.SAMPLE_INTERVAL_METERS
    )
    heights = [record["elevation_ft"] for record in records]
    share = sum(height is None for height in heights) / len(heights)
    assert _share_outside_fixtures() < share < float(build_marts.FIXTURE_PROFILE_MAX_NULL_SHARE)
    assert _passes("pub_elevation_profile", _profile(heights), float(build_marts.FIXTURE_PROFILE_MAX_NULL_SHARE))
    assert not _passes("pub_elevation_profile", _profile(heights), _share_outside_fixtures())
