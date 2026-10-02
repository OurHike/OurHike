"""The sources family's SQL refuses what export_sources.py refuses, on the same rows (#1793, stage 3).

stewards.json and registry.json moved to SQL (pipeline/ELT.md's sources rule
table, SR01-SR07), and until stage 5 deletes the Python both are live. parity.py
compares the two files on the real registry in CI; this holds the parts the
real registry never exercises, because every one of them is a refusal:

- the surfaces seed and the two pattern vars are export_sources.py's constants;
- each unit test's mocked seed rows are that seed file, row for row;
- `_paper_maps`, run over int_sources__paper_maps's unit-test tables, refuses
  the same tables with the same words, except where DELIBERATE says the SQL
  is stricter on purpose;
- build_output(), run over int_sources__stewards's unit-test registry one
  provider at a time, names the same steward and refuses the same blocks with
  the same words, except the one the SQL words differently.
"""

import csv
import json
import re
from pathlib import Path

import pytest
import yaml

import export_sources

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "sources" / "_sources__intermediate.yml"

# Paper-map tables the SQL refuses and `_paper_maps` publishes: a sheet number
# and a handle with a trailing newline, which re.match's `$` lets through.
DELIBERATE = {"reference/maps_16.json", "reference/maps_17.json"}

# Refused by both, in different words: SQL sees the warehouse, so it says no
# resource lands the table, where the Python says the file is not there.
DIFFERENT_WORDS = {"H"}

BLOCK = re.compile(
    r"select '((?:[^']|'')*)' as entry_name, (\d+) as entry_position, .*? cast\('((?:[^']|'')*)' as json\) as entry_value"
)


def _unit_test(name: str) -> dict:
    return next(test for test in yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"] if test["name"] == name)


def _given(test: dict, model: str) -> dict:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")


def _same_words(message: str) -> str:
    """A message with Python's repr and JSON told apart only by quotes, spaces and the names of true and null."""
    return re.sub(r"\s+", "", message.replace("'", '"')).replace("True", "true").replace("None", "null")


def _refusal(call) -> str | None:
    """The first line of the SystemExit `call` raises, or None if it returns."""
    try:
        call()
    except SystemExit as refused:
        return str(refused).split("\n", 1)[0]
    return None


def _seed() -> list[dict]:
    with (DBT / "seeds" / "registry_surfaces.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_the_surfaces_seed_is_the_two_closed_vocabularies():
    rows = _seed()
    assert {row["surface"] for row in rows if row["block_kind"] == "support"} == export_sources.DONATE_SURFACES
    assert {row["surface"] for row in rows if row["block_kind"] == "store"} == export_sources.STORE_SURFACES
    assert {row["block_kind"] for row in rows} == {"support", "store"}


def test_the_pattern_vars_are_the_python_patterns():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["registry_product_handle_pattern"] == export_sources.PRODUCT_HANDLE.pattern
    assert variables["registry_sheet_number_pattern"] == export_sources.SHEET_NUMBER.pattern


def test_the_stewards_unit_tests_mocked_seed_is_the_seed_file():
    test = _unit_test("int_sources__stewards_refuses_what_export_sources_refuses")
    assert _given(test, "registry_surfaces")["rows"] == _seed()


def _paper_map_tables() -> dict[str, dict]:
    test = _unit_test("int_sources__paper_maps_refuses_what_paper_maps_refuses")
    return {
        row["file_path"]: json.loads(row["document_json"]) for row in _given(test, "base_registry__nynjtc_paper_maps")["rows"]
    }


def test_paper_maps_refuses_what_the_unit_test_expects():
    expected = {
        row["file_path"]: row["problem"]
        for row in _unit_test("int_sources__paper_maps_refuses_what_paper_maps_refuses")["expect"]["rows"]
    }
    tables = _paper_map_tables()
    assert set(expected) == set(tables)
    for path, table in tables.items():
        python = _refusal(lambda: export_sources._paper_maps(table, Path(path)))
        if path in DELIBERATE:
            assert python is None and expected[path] is not None, f"{path} is no longer a deliberate difference"
            continue
        assert (python is None) == (expected[path] is None), f"{path}: Python {python!r}, SQL {expected[path]!r}"
        if python is not None:
            assert _same_words(python) == _same_words(expected[path]), path


@pytest.fixture
def unit_registry(tmp_path):
    """The stewards unit test's registry as sources.json would hold it, and its paper-map tables on disk."""
    test = _unit_test("int_sources__stewards_refuses_what_export_sources_refuses")
    sources = [
        {
            "key": row["source_key"],
            "provider": row["provider"],
            "reaches_hikers": row["reaches_hikers"],
            **({"steward": row["steward"]} if row.get("steward") is not None else {}),
        }
        for row in _given(test, "stg_registry__sources")["rows"]
    ]
    blocks = sorted(
        (int(position), name.replace("''", "'"), json.loads(block.replace("''", "'")))
        for name, position, block in BLOCK.findall(_given(test, "stg_registry__top_level")["rows"])
    )
    assert blocks, "no block parsed out of the unit test's top-level rows"
    for path, table in _paper_map_tables().items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(json.dumps(table))
    return {"sources": sources, **{name: block for _, name, block in blocks}}, tmp_path, test["expect"]["rows"]


def test_build_output_names_and_refuses_what_the_unit_test_expects(unit_registry):
    registry, reference_dir, expected = unit_registry
    by_provider = {row["provider"]: row for row in expected}
    providers = {source["provider"] for source in registry["sources"]}
    for provider in sorted(providers):
        alone = {**registry, "sources": [s for s in registry["sources"] if s["provider"] == provider]}
        output: dict = {}
        python = _refusal(lambda alone=alone: output.update(export_sources.build_output(alone, reference_dir=reference_dir)))
        if provider not in by_provider:
            assert python is None and output["stewards"] == [], f"{provider} ships nothing, so it has no record"
            continue
        row = by_provider[provider]
        assert (python is None) == (row["problem"] is None), f"{provider}: Python {python!r}, SQL {row['problem']!r}"
        if python is None:
            assert output["stewards"][0]["name"] == row["steward_name"], provider
        elif provider not in DIFFERENT_WORDS:
            python = python.replace(f"{reference_dir}/", "")
            assert _same_words(python) == _same_words(row["problem"]), provider


# The bases that publish nothing because nobody has settled them (pipeline/ELT.md,
# "The eleven marts", `may_publish`): sources.json's `unresolved`, and
# trail_orgs.json's `unstated` once that file lands.
UNSETTLED_BASES = {"unresolved", "unstated"}


def test_every_licence_basis_the_registry_uses_is_classified_for_may_publish():
    """A basis int_sources__publication has never been told about must not publish by accident.

    The model refuses any basis the publishable_licence_bases seed does not list,
    which is the cautious direction, but a new basis would then hold its sources
    back with nobody having decided that. So each basis sources.json uses is
    either a seed row or one of the unsettled values, and adding a fifth means
    deciding which.
    """
    with (DBT / "seeds" / "publishable_licence_bases.csv").open(newline="") as handle:
        publishable = {row["licence_basis"] for row in csv.DictReader(handle)}
    registry = json.loads((DBT.parent / "sources.json").read_text())
    used = {source.get("licence_basis") for source in registry["sources"]}
    assert used - publishable - UNSETTLED_BASES == set()
    assert not publishable & UNSETTLED_BASES


def test_an_unregistered_publishing_source_is_not_also_registered():
    """unregistered_publishing_sources is for sources with no sources.json row, and only those.

    A key in both would have two answers to "may it publish", and the registry's
    is the one that should win, so the seed row would be a stale exception.
    """
    with (DBT / "seeds" / "unregistered_publishing_sources.csv").open(newline="") as handle:
        unregistered = {row["source_key"] for row in csv.DictReader(handle)}
    registry = json.loads((DBT.parent / "sources.json").read_text())
    assert unregistered.isdisjoint({source["key"] for source in registry["sources"]})
    assert unregistered, "the seed is empty: drop it and this test rather than keep an empty exception list"
