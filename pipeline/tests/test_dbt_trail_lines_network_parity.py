"""The network's SQL answers what export_nearby_trails.py answers, on the same rows (#1793, stage 3).

The network half of trail_lines moved to SQL (pipeline/ELT.md's trail_lines
rule table, the TL rows for export_nearby_trails.py), and until stage 5
deletes the Python both are live. parity.py compares the two writers' files on
the fixture warehouse in CI; this holds the branches the fixtures never reach,
by running the Python over each dbt unit test's own rows:

- int_trail_lines__blazes: lib/blaze.py's normalize_blaze_color() and
  map_source_blaze() as export_trails.py's normalize_source_features()
  composes them for the A.T., and export_nearby_trails.py's resolve_blaze()
  for the network, give the colour, decode and disposition the unit test
  expects on every row;
- the palette the blaze test holds a mapped colour to is lib/blaze.py's.

dbt runs the other half: each unit test holds the SQL to those expectations.
"""

import json
from pathlib import Path

import pytest
import yaml

import export_nearby_trails
import export_trails
from lib import blaze

DBT = Path(__file__).parent.parent / "dbt"
NETWORK_YML = DBT / "models" / "intermediate" / "trail_lines" / "_trail_lines__network.yml"


def _document() -> dict:
    return yaml.safe_load(NETWORK_YML.read_text())


def _unit_test(name: str) -> dict:
    return next(test for test in _document()["unit_tests"] if test["name"] == name)


def _given(test: dict, model: str) -> list[dict]:
    return next(given["rows"] for given in test["given"] if given["input"] == f"ref('{model}')")


def _expected(test: dict) -> dict[str, dict]:
    return {row["trail_segment_key"]: row for row in test["expect"]["rows"]}


def _model(name: str) -> dict:
    return next(model for model in _document()["models"] if model["name"] == name)


# --- int_trail_lines__blazes (TL03) ---------------------------------------------

BLAZES = "int_trail_lines__blazes_answers_what_lib_blaze_answers"


def test_a_mapped_blaze_is_held_to_lib_blaze_palette_and_neutrals():
    column = next(c for c in _model("int_trail_lines__blazes")["columns"] if c["name"] == "blaze_color")
    (accepted,) = [
        test["accepted_values"] for test in column["data_tests"] if isinstance(test, dict) and "accepted_values" in test
    ]
    assert accepted["arguments"]["values"] == [*blaze.PALETTE, *blaze.NEUTRAL_MEMBERS]
    assert accepted["config"]["where"] == "blaze_disposition = 'mapped'"


def test_every_unit_test_row_has_an_expectation():
    test = _unit_test(BLAZES)
    keys = [
        row["trail_segment_key"]
        for model in ("stg_atc__centerline_segments", "stg_atc__side_trails", "int_trail_lines__network_unioned")
        for row in _given(test, model)
    ]
    assert sorted(keys) == sorted(_expected(test))


def test_the_at_rows_decode_and_map_as_export_trails_does(monkeypatch):
    """normalize_source_features(), with the live domain call and the reviewed
    file replaced by the unit test's own: the colour it attaches is the one the
    SQL expects, and the decode and disposition are those of the two lib/blaze.py
    calls it makes, in its order."""
    test = _unit_test(BLAZES)
    registry = {row["source_key"]: json.loads(row["entry"]) for row in _given(test, "stg_registry__sources")}
    (document,) = _given(test, "base_ourhike__blaze_mapping")
    mapping = json.loads(document["document_json"])["sources"]
    # side_trails' Blaze is esriFieldTypeString with codes '0' to '9' (tl-at,
    # 2026-10-02, from the live layer's domain), so the codes and the values
    # are both strings, as the unit test's rows hold them.
    domain = {row["code"]: row["label"] for row in _given(test, "int_trail_lines__coded_domains")}
    monkeypatch.setattr(export_trails, "get_field_coded_domain", lambda url, field: domain)
    monkeypatch.setattr(export_trails, "load_blaze_mapping", lambda: mapping)
    expected = _expected(test)

    rows = [(row, "centerline") for row in _given(test, "stg_atc__centerline_segments")]
    rows += [(row, "side_trails") for row in _given(test, "stg_atc__side_trails")]
    for row, key in rows:
        source = {"url": "https://example.test/at", **registry[key]}
        field = source.get("blaze_field")
        properties = {field: row.get("blaze")} if field else {}
        (normalized,) = export_trails.normalize_source_features(source, [{"properties": properties}])

        colour, decoded = blaze.normalize_blaze_color(
            properties.get(field) if field else None, domain if field else None, source.get("blaze_default")
        )
        disposition = None
        if mapping.get(key) is not None and decoded:
            colour, disposition = blaze.map_source_blaze(colour, mapping[key])
        assert normalized["_blaze_color"] == colour, row["trail_segment_key"]

        want = expected[row["trail_segment_key"]]
        assert (want["blaze_color"], want["blaze_decoded"], want["blaze_disposition"]) == (colour, decoded, disposition), row[
            "trail_segment_key"
        ]


def test_the_network_rows_resolve_as_resolve_blaze_does():
    """resolve_blaze() on each row's properties, read back under the registry's
    spelling of the field. Its 'default', for a source with no blaze field, is
    the SQL's null: the lead's column spec gives such a row no disposition."""
    test = _unit_test(BLAZES)
    (document,) = _given(test, "base_ourhike__blaze_mapping")
    mapping = json.loads(document["document_json"])["sources"]
    sources = {row["source_key"]: row for row in _given(test, "int_trail_lines__network_sources")}
    expected = _expected(test)

    for row in _given(test, "int_trail_lines__network_unioned"):
        declared = sources[row["source_key"]]
        source = {key: declared[key] for key in ("blaze_field", "blaze_default") if declared.get(key) is not None}
        landed = json.loads(row["properties"])
        properties = (
            {declared["blaze_field"]: landed[declared["blaze_column"]]}
            if "blaze_column" in declared and declared["blaze_column"] in landed
            else {}
        )
        colour, disposition = export_nearby_trails.resolve_blaze(source, properties, mapping.get(row["source_key"]))
        want = expected[row["trail_segment_key"]]
        assert want["blaze_decoded"] is True, row["trail_segment_key"]
        assert (want["blaze_color"], want["blaze_disposition"]) == (colour, None if disposition == "default" else disposition), (
            row["trail_segment_key"]
        )


@pytest.mark.parametrize("raw", ["Teal", "Pink", "Chartreuse"])
def test_a_reviewed_value_answers_the_same_whichever_export_asks(raw):
    """The two exports reach map_source_blaze() by different paths and must not
    disagree about one table: export_trails.py maps a decoded label, resolve_blaze()
    a raw value, and for a value that needs no decode the two are one call."""
    table = {"mapped": {"Teal": "Aqua"}, "deferred": {"Pink": {}}}
    source = {"blaze_field": "Blaze"}
    assert export_nearby_trails.resolve_blaze(source, {"Blaze": raw}, table) == blaze.map_source_blaze(raw, table)
