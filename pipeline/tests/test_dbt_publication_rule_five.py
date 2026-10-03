"""Rule 5's two seeds, held without a warehouse (pipeline/ELT.md, "Who may publish", rule 5; decision 53's phase C).

int_sources__publication reads licence_restriction_phrases and
licence_restriction_answers to hold back a source whose quoted words carry a
restriction no decision answers. Its unit tests mock both seeds; this file
holds the mocks to the seed files row for row, so a unit test cannot pass on a
vocabulary the build does not use, and checks what each row claims about
itself: every pattern compiles in DuckDB's RE2, and a phrase that names the
registry row it was written for finds its words in that row.
"""

import csv
import json
from pathlib import Path

import duckdb
import pytest
import yaml

PIPELINE = Path(__file__).resolve().parent.parent
DBT = PIPELINE / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "sources" / "_sources__intermediate.yml"
SEEDS = ("licence_restriction_phrases", "licence_restriction_answers")
PUBLICATION_TESTS = (
    "int_sources__publication_publishes_only_what_a_rule_makes_true",
    "int_sources__publication_holds_words_no_decision_answers",
)


def _seed(name: str) -> list[dict]:
    with (DBT / "seeds" / f"{name}.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def _unit_test(name: str) -> dict:
    tests = {test["name"]: test for test in yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"]}
    return tests[name]


def _given(test: dict, name: str) -> list[dict]:
    return next(given["rows"] for given in test["given"] if given["input"] == f"ref('{name}')")


def _registry() -> dict[str, dict]:
    return {row["key"]: row for row in json.loads((PIPELINE / "sources.json").read_text())["sources"]}


@pytest.mark.parametrize("test_name", PUBLICATION_TESTS)
@pytest.mark.parametrize("seed", SEEDS)
def test_each_unit_tests_mocked_seed_is_the_seed_file(test_name, seed):
    mocked = [
        {name: ("" if value is None else value) for name, value in row.items()} for row in _given(_unit_test(test_name), seed)
    ]
    assert mocked == _seed(seed)


@pytest.mark.parametrize(
    ("seed", "column"),
    [("licence_restriction_phrases", "pattern"), ("licence_restriction_answers", "named_by")],
)
def test_every_pattern_compiles_as_duckdb_reads_it(seed, column):
    con = duckdb.connect()
    for row in _seed(seed):
        con.execute("select regexp_matches('', ?, 'i')", [row[column]])


def test_every_phrase_written_for_a_row_finds_its_words_in_that_row():
    """A phrase's `written_for` is a provenance claim: its pattern matches the words that registry row quotes."""
    registry = _registry()
    con = duckdb.connect()
    for row in _seed("licence_restriction_phrases"):
        key = row["written_for"]
        if not key:
            continue
        assert key in registry, f"{row['pattern']}: written_for {key!r} is not a sources.json key"
        words = " ".join(part for part in (registry[key].get("terms"), registry[key].get("terms_verbatim")) if part)
        (found,) = con.execute("select regexp_matches(?, ?, 'i')", [words, row["pattern"]]).fetchone()
        assert found, f"{row['pattern']} does not match the words {key} quotes"


def test_no_answer_row_answers_what_decision_38_holds_or_the_backstop():
    """`cannot_be_met` and `unclassified` hold their row whatever its licence says, so neither has an answer."""
    restrictions = {row["restriction"] for row in _seed("licence_restriction_answers")}
    assert not restrictions & {"cannot_be_met", "unclassified", "not_a_restriction"}


def test_there_is_exactly_one_backstop():
    assert [row["restriction"] for row in _seed("licence_restriction_phrases")].count("unclassified") == 1
