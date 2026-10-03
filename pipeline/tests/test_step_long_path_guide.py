"""step_long_path_guide.py: NYNJTC's Long Path guide placed as waypoints, into derived.long_path_guide (PO36).

The rule is lib/nynjtc_long_path_guide.py's build_records() and its own
tests hold it (tests/test_nynjtc_long_path_guide.py); these hold the step to
it on make_dbt_fixtures.py's guide pages, parsed as the guide_pages kind
parses them: the sections and lines read back from the warehouse as the
module reads them, every record landed whole, and no network reached.
"""

import json
from datetime import UTC, datetime

import duckdb
import pytest

import make_dbt_fixtures
import step_long_path_guide
from lib import nynjtc_long_path_guide as guide

LOADED = datetime(2026, 10, 2, tzinfo=UTC)


@pytest.fixture
def inputs(tmp_path):
    """The fixture's parsed sections and Long Path features, and a warehouse holding both as the staging models do."""
    raw = tmp_path / "raw"
    make_dbt_fixtures.write_fixtures(raw)
    folder = raw / "guide_pages" / guide.SOURCE_KEY
    files = json.loads((folder / "pages.json").read_text())
    index = (folder / files[guide.INDEX_URL]).read_text()
    sections = [
        guide.parse_section((folder / files[url]).read_text(), url, expected_number=number)
        for number, url in guide.parse_index(index)
    ]
    features = json.loads((raw / "external" / "nynjtc_long_path.geojson").read_text())["features"]
    warehouse = tmp_path / "w.duckdb"
    with duckdb.connect(str(warehouse)) as con:
        con.execute("install spatial; load spatial; create schema staging")
        con.execute(
            "create table staging.stg_nynjtc__long_path_guide (section_number integer, title varchar, distance_miles double, "
            "parks varchar, url varchar, parking json, camping json, entries json, notes json)"
        )
        # Landed out of order: the step reads them back in section order, as the extract's index walk lists them.
        for section in reversed(sections):
            data = section.to_dict()
            con.execute(
                "insert into staging.stg_nynjtc__long_path_guide values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    data["number"],
                    data["title"],
                    data["distance_miles"],
                    data["parks"],
                    data["url"],
                    json.dumps(data["parking"]),
                    json.dumps(data["camping"]),
                    json.dumps(data["description"]),
                    json.dumps(data["notes"]),
                ],
            )
        con.execute("create table staging.stg_nynjtc__long_path (source_row integer, lp_section varchar, geom geometry)")
        for row, feature in enumerate(features):
            con.execute(
                "insert into staging.stg_nynjtc__long_path values (?, ?, st_geomfromgeojson(?))",
                [row, feature["properties"].get("LP_Section"), json.dumps(feature["geometry"])],
            )
    return sections, features, warehouse


def test_the_step_lands_what_build_records_makes_of_the_same_inputs(inputs):
    sections, features, warehouse = inputs
    assert step_long_path_guide.main(["--warehouse", str(warehouse)]) == 0
    expected, _ = guide.build_records(sections, features)
    with duckdb.connect(str(warehouse), read_only=True) as con:
        rows = con.execute(
            "select record_row, id, lat, lon, confidence, record from derived.long_path_guide order by record_row"
        ).fetchall()
    assert [json.loads(row[5]) for row in rows] == expected
    assert [(row[1], row[2], row[3], row[4]) for row in rows] == [
        (record["id"], record["lat"], record["lon"], record["confidence"]) for record in expected
    ]


def test_the_fixture_guide_reaches_every_branch_build_records_has(inputs):
    sections, features, _ = inputs
    records, stats = guide.build_records(sections, features)
    assert {"stated", "interpolated"} == {record["placement"] for record in records}
    assert stats["duplicates_merged"] >= 3, "a lean-to named twice, a boundary lot, a campsite at the same mile"
    assert {
        "coordinates outside the Long Path's extent (a typo on the page)",
        "mile past the section's stated distance",
        "camping: no place in the entry",
        "marked (unlocated) by NYNJTC",
        "section 5 states no distance",
        "section 6 has no line in the layer",
    } <= set(stats["skipped"])
    assert any("off_trail_miles" in record for record in records)
    assert {record.get("water_reliability") for record in records if record["poi_type"] == "water"} >= {"reliable", "unreliable"}


def test_the_lines_come_back_as_section_lines_reads_them(inputs):
    _, features, warehouse = inputs
    with duckdb.connect(str(warehouse), read_only=True) as con:
        con.execute("load spatial")
        lines = step_long_path_guide.read_lines(con)
    assert guide.section_lines(lines) == guide.section_lines(features)


def test_the_step_refuses_to_run_before_its_inputs_are_built(tmp_path):
    duckdb.connect(str(tmp_path / "w.duckdb")).close()
    with pytest.raises(SystemExit, match="stg_nynjtc__long_path_guide"):
        step_long_path_guide.main(["--warehouse", str(tmp_path / "w.duckdb")])
