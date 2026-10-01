"""int_podcasts__checked finds what lib/podcasts.py's validate() finds, on the same rows (#1793, stage 3).

The podcasts gate moved to SQL (pipeline/ELT.md's podcasts rule table,
PC01-PC12), and until stage 5 deletes the Python both are live: export_podcasts.py
still uploads, and the dbt writer's file is compared with its output by
parity.py. Two copies of one rule drift unless something holds them
together, and this is that something, in three parts:

- the seeds and vars the model reads are lib/podcasts.py's constants;
- the unit test's mocked seeds are those seed files, row for row, so the unit
  test cannot pass against a seed the build no longer has;
- validate(), run over the unit test's own rows and ledger, reports the rule
  the unit test expects on every row, and the same words, except on the rows
  DELIBERATE lists, where the SQL is stricter on purpose.

dbt runs the other half: the unit test holds the SQL to those expectations.
"""

import csv
import json
import re
from pathlib import Path

import pytest
import yaml

from lib import podcasts

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "podcasts" / "_podcasts__intermediate.yml"

# The rows on which validate() publishes and the SQL refuses, each for a reason
# int_podcasts__checked.sql's header gives. Each is an improvement: a value the
# file's own documentation does not allow.
DELIBERATE = {
    36: "reviewed 20260929: date.fromisoformat() takes it, the message says YYYY-MM-DD",
    37: "a trailing newline after the id: re.match's $ matches before it",
    39: "a link with a leading space: urlsplit() strips it, and the phone would open the link with it",
}

# validate()'s messages, to the rule numbers pipeline/ELT.md gives them. First match wins.
RULES = [
    (r"^not an object$", "PC08"),
    (r"^unknown field\(s\) ", "PC03"),
    (r"^spotify_id must be ", "PC01"),
    (r"^the same episode is listed twice", "PC06"),
    (r"^title and show are both required$", "PC08"),
    (r"^needs at least one of ", "PC12"),  # before PC02 and PC05: it names at_miles and pois
    (r"^minutes must be ", "PC09"),
    (r"^hikes must be ", "PC10"),
    (r"at_miles", "PC02"),
    (r"^pois |^places |POI|was retired on ", "PC05"),
    (r"^links", "PC04"),
    (r"^reviewed ", "PC11"),
]


def _rule(message: str) -> str:
    return next(rule for pattern, rule in RULES if re.search(pattern, message))


def _same_words(message: str) -> str:
    """A message with Python's repr and JSON told apart only by quotes, spaces and the names of true and null."""
    return re.sub(r"\s+", "", message.replace("'", '"')).replace("True", "true").replace("None", "null")


def _unit_test() -> dict:
    (test,) = yaml.safe_load(UNIT_TESTS.read_text())["unit_tests"]
    return test


def _given(name: str) -> list[dict]:
    return next(given["rows"] for given in _unit_test()["given"] if given["input"] == f"ref('{name}')")


def _seed(name: str) -> list[dict]:
    with (DBT / "seeds" / f"{name}.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_the_field_seed_is_row_fields():
    assert {row["field_name"] for row in _seed("podcast_row_fields")} == podcasts.ROW_FIELDS


def test_the_host_seed_is_app_link_hosts():
    hosts: dict[str, set[str]] = {}
    for row in _seed("podcast_app_link_hosts"):
        hosts.setdefault(row["app"], set()).add(row["hostname"])
    assert hosts == {app: set(names) for app, names in podcasts.APP_LINK_HOSTS.items()}


def test_the_vars_are_the_python_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["podcast_spotify_id_pattern"] == podcasts.SPOTIFY_ID_PATTERN.pattern
    assert float(variables["podcast_max_at_mile"]) == podcasts.MAX_AT_MILE


@pytest.mark.parametrize("seed", ["podcast_row_fields", "podcast_app_link_hosts"])
def test_the_unit_tests_mocked_seeds_are_the_seed_files(seed):
    assert _given(seed) == _seed(seed)


def test_validate_finds_what_the_unit_test_expects():
    rows = sorted(_given("base_podcasts__podcast_episodes"), key=lambda row: row["file_row"])
    assert [row["file_row"] for row in rows] == list(range(len(rows)))
    ledger = {
        row["poi_id"]: {name: value for name, value in row.items() if name != "poi_id" and value is not None}
        for row in _given("base_ourhike__poi_identity")
    }
    result = podcasts.validate([json.loads(row["episode"]) for row in rows], ledger)
    python = {int(re.match(r"row (\d+)", label).group(1)): message for label, message in result.dropped}

    expected = {row["file_row"]: row for row in _unit_test()["expect"]["rows"]}
    assert set(expected) == set(range(len(rows)))
    for at, row in expected.items():
        if at in DELIBERATE:
            assert at not in python and row["rule_id"] is not None, f"row {at} is no longer a deliberate difference"
            continue
        if row["rule_id"] is None:
            assert at not in python, f"row {at}: validate() drops it ({python.get(at)}), the SQL keeps it"
            continue
        assert at in python, f"row {at}: validate() keeps it, the SQL refuses it ({row['problem']})"
        assert _rule(python[at]) == row["rule_id"], f"row {at}: {python[at]!r}"
        assert _same_words(python[at]) == _same_words(row["problem"]), f"row {at}"
