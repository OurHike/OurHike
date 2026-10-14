"""NGPC's Cowboy Trail: one 29-section status layer is both its closures and its line.

The maintainer's P7+P8 on wave 6's review page 01 (poll of 2026-10-11): NGPC ships, and the Cowboy Trail draws from
the commission's section layer, `ngpc_cowboy_trail_improvements` (Cowboy_Trail/FeatureServer/5), developed trail
only; the 321-mile corridor line must never draw as trail. What holds that here, without a warehouse:

- the corridor line, Cowboy_Trail_Complete, is registered by no sources.json row, and a builder takes a registered
  key and nothing else (extract/_kinds.py), so no resource reads it and no line of it reaches the trail_lines mart,
  the network or the junction graph;
- the layer_rules seed draws a section only where its Road_Status is 'Open' or 'Closed', so the two 'Alt Route'
  sections, the HWY 275 detour, never draw as trail;
- the line closes on exactly the values the closures read as closing the trail, so the map's barred band and the
  closures list cannot disagree about a section;
- the layer is one extraction on the hourly lane, and the monthly lane lands its own copy for the line.

The rules themselves are dbt unit tests (dbt/models/intermediate/trail_lines/_trail_lines__club_lines.yml: the
section kinds, and the closed section's status), and dbt's assert_no_club_line_is_a_graph_edge holds that no club
line, these among them, is an edge of the junction graph.
"""

import csv
import json
from pathlib import Path

import generate_notice_models
import make_dbt_staging
from extract._contract import all_resources, discover, discover_shared
from extract._run import ALSO_READS, lane_resources

PIPELINE = Path(__file__).resolve().parent.parent
SEEDS = PIPELINE / "dbt" / "seeds"
KEY = "ngpc_cowboy_trail_improvements"
TABLE = f"raw_ngpc__{KEY}"
#: The corridor line's service: one feature, 321.33 miles, 'GIS Value', edited 2016-10-05 (the coverage audit,
#: quoted in extract/not_available.toml's [ngpc.trail_lines]).
CORRIDOR = "Cowboy_Trail_Complete"


def _seed(name: str) -> list[dict]:
    with (SEEDS / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_the_cowboy_trail_corridor_line_is_registered_by_no_row_so_no_resource_reads_it():
    """No sources.json row points any URL at the corridor's service, and every resource reads a registered key's URL."""
    registry = json.loads((PIPELINE / "sources.json").read_text())["sources"]

    def points_at_corridor(row: dict) -> bool:
        return any(isinstance(value, str) and value.startswith("https://") and CORRIDOR in value for value in row.values())

    assert [row["key"] for row in registry if points_at_corridor(row)] == []
    registered = {row["key"] for row in registry}
    layers = {resource.key for resource in all_resources(discover()) if resource.club == "ngpc" and resource.type != "org"}
    assert KEY in layers and layers <= registered


def test_the_cowboy_trail_draws_only_its_open_and_closed_sections():
    """keep_only_where reads case and surrounding space aside, and leaves out a value it does not name: 'Alt Route'."""
    kept = {
        (row["field"], row["matches"])
        for row in _seed("layer_rules")
        if row["source_key"] == KEY and row["rule"] == "keep_only_where"
    }
    assert kept == {("road_status", "Open"), ("road_status", "Closed")}


def test_a_line_closes_on_exactly_the_values_its_closures_read_as_closing_the_trail():
    """For each layer the layer_rules seed closes lines on, and whose notices the two value seeds read: the
    closed_where values are the values those seeds read as closes_trail, field by field (dlt's names), so the line
    and the closures list close the same sections. NGPC's is the one today."""
    fields = {row["source_key"]: row for row in _seed("notice_source_fields")}
    closing: dict[str, set[tuple[str, str]]] = {}
    for seed, role in (("notice_status_values", "status"), ("notice_category_values", "category")):
        value_column = f"{role}_value"
        for row in _seed(seed):
            if row["reads_as"] != "closes_trail" or not fields.get(row["source_key"], {}).get(role):
                continue
            field = generate_notice_models._normalize(fields[row["source_key"]][role])
            closing.setdefault(row["source_key"], set()).add((field, row[value_column].strip().lower()))
    closed_where: dict[str, set[tuple[str, str]]] = {}
    for row in _seed("layer_rules"):
        if row["rule"] == "closed_where":
            closed_where.setdefault(row["source_key"], set()).add((row["field"], row["matches"].strip().lower()))
    assert KEY in closed_where and KEY in closing
    for source_key, values in closed_where.items():
        if source_key in closing:
            assert values == closing[source_key], source_key
    assert closed_where[KEY] == {("road_status", "closed"), ("condition", "impassable"), ("condition", "not passable")}


def test_the_sections_are_one_extraction_on_the_hourly_lane_and_the_monthly_lane_lands_its_own_copy():
    resources = [resource for resource in all_resources(discover() + discover_shared()) if resource.key == KEY]
    assert [(resource.club, resource.type, resource.table) for resource in resources] == [("ngpc", "closures", TABLE)]
    assert [resource.table for resource in lane_resources("hourly", resources)] == [TABLE]
    assert TABLE in ALSO_READS["monthly"]
    staged = [table for table in make_dbt_staging.tables() if table.key == KEY]
    assert [(table.type, table.cadence, table.lane_copy) for table in staged] == [("trail_lines", "monthly", True)]
    assert {source.table for source in generate_notice_models.notice_sources()} >= {TABLE}
