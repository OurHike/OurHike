"""Every row in the evaluator's exceptions seed says why, and names its issue.

dbt_project_evaluator is enforced (dbt/dbt_project.yml), so a finding gets
fixed or gets a row in dbt/seeds/dbt_project_evaluator_exceptions.csv. A row
is a rule switched off for the models it matches, and nothing in dbt asks
for a reason: the package's own `comment` column is optional. This file
makes the reason structural, as the seed's description in seeds.yml
promises (#1793 — Rebuild the data platform as dlt → dbt: seven contracted
marts, a monthly refresh, published docs, and lighter phone downloads):

- every column is filled, and `comment` is a sentence, not a word;
- the comment cites at least one issue by number AND title, CLAUDE.md's
  form ("#N — Title"), because a bare number here is not even reliably an
  issue;
- `id_to_exclude` is a LIKE pattern that names something. A pattern made
  only of `%` and `_` would match every finding of its rule, and a quote in
  it would break the SQL filter_exceptions() writes it into.

What this cannot check: that a title is the issue's current title (no
network in tests), or that a pattern matches only the models its comment
means. The evaluator run in CI's `dbt` job is what shows the pattern is not
too narrow; nothing shows it is not too wide except reading it.
"""

import csv
import re
from pathlib import Path

SEED_PATH = Path(__file__).parent.parent / "dbt" / "seeds" / "dbt_project_evaluator_exceptions.csv"
COLUMNS = ["fct_name", "column_name", "id_to_exclude", "comment"]

#: "#1793 — Rebuild ...": a number, an em dash, then a title of a few words.
ISSUE_WITH_TITLE = re.compile(r"#\d+ — \S+(?: \S+){2,}")
#: The digits are held whole by the (?!\d): without it, \d+ backs off one
#: digit and reads "#1793 — ..." as a bare "#179".
BARE_ISSUE = re.compile(r"#\d+(?!\d| — )")


def _rows():
    with open(SEED_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS, f"the evaluator reads exactly these columns: {COLUMNS}"
        return list(reader)


def test_every_column_of_every_row_is_filled():
    for row in _rows():
        assert all(row[c].strip() for c in COLUMNS), row
        assert row["fct_name"].startswith("fct_"), f"{row['fct_name']} is not an evaluator finding model"


def test_every_comment_gives_a_reason_and_names_an_issue_with_its_title():
    for row in _rows():
        comment = row["comment"]
        assert len(comment.split()) >= 12, f"{row['id_to_exclude']}: a reason is a sentence, not {comment!r}"
        assert ISSUE_WITH_TITLE.search(comment), (
            f"{row['id_to_exclude']}: cite the issue as '#N — Title' (CLAUDE.md), so a reader can judge it unopened"
        )
        assert not BARE_ISSUE.search(comment), f"{row['id_to_exclude']}: every #N in the comment needs its title"


def test_no_pattern_switches_a_whole_rule_off():
    for row in _rows():
        pattern = row["id_to_exclude"]
        assert pattern.strip("%_"), f"{row['fct_name']}: {pattern!r} matches every finding of the rule"
        assert "'" not in pattern, f"{pattern!r}: filter_exceptions() writes the pattern into SQL between quotes"


def test_the_rules_are_caught_by_the_checks_above():
    """The three checks, run against rows they must refuse, so a loosened
    regex cannot pass every row by passing everything."""
    assert not ISSUE_WITH_TITLE.search("see #1793")
    assert BARE_ISSUE.search("see #1793 for why")
    assert not BARE_ISSUE.search("see #1793 — Rebuild the data platform")
    assert ISSUE_WITH_TITLE.search("see #1793 — Rebuild the data platform")
    assert not "%_%".strip("%_")
