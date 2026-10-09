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

A ROW THAT CAN NO LONGER MATCH ANYTHING is a rule switched off in advance for
whatever later takes the name. The review of PR #1805 (dlt → dbt re-platform
as one go/no-go change) ran the evaluator with an empty seed on 2026-10-09 and
found 11 of 54 rows matching no finding. So every row's pattern must match a
resource the parsed project has, named as the evaluator names it
(int_all_graph_resources.sql: `source_name.name` for a source, `name.vN` for a
versioned model, else `name`). That catches a row whose resource was renamed,
deleted or versioned: 4 of those 11, rows naming closures, warnings,
points_of_interest and trail_lines after those marts became closures.v1 and
the rest. It cannot catch a row whose resource still exists but whose finding
is gone, because the model was fixed (the other 7: five staging models given
key tests, pub_trail_miles once pub_trails_geojson gained a second child,
int_sources__publication once the conditions writers stopped reading it). Only
an unfiltered evaluator run shows those, which is minutes of build, not a test:
`dbt build -s package:dbt_project_evaluator` over an empty copy of the seed,
then each row's LIKE against its finding table. It needs a parsed manifest, so
it runs only where OURHIKE_DBT names dbt 2.0.6 (pipeline-tests.yml's dbt job
and scripts/test.sh's dbt suite); the name matching itself is tested here
without one.
"""

import csv
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

DBT_DIR = Path(__file__).parent.parent / "dbt"
SEED_PATH = DBT_DIR / "seeds" / "dbt_project_evaluator_exceptions.csv"
COLUMNS = ["fct_name", "column_name", "id_to_exclude", "comment"]
DBT = os.environ.get("OURHIKE_DBT")

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


def _like(pattern: str) -> re.Pattern:
    """A SQL LIKE pattern with no ESCAPE clause, as filter_exceptions() writes it: `%` any run, `_` any one character."""
    return re.compile("".join(".*" if c == "%" else "." if c == "_" else re.escape(c) for c in pattern), re.DOTALL)


def _resource_names(manifest: dict) -> dict[str, set[str]]:
    """Every name a finding can carry, by kind, as the evaluator writes it (int_all_graph_resources.sql)."""
    nodes = {
        f"{node['name']}.v{node['version']}" if node.get("version") is not None else node["name"]
        for node in (manifest.get("nodes") or {}).values()
        if node.get("resource_type") in ("model", "seed", "snapshot")
    }
    sources = {f"{source['source_name']}.{source['name']}" for source in (manifest.get("sources") or {}).values()}
    exposures = {exposure["name"] for exposure in (manifest.get("exposures") or {}).values()}
    return {"nodes": nodes, "sources": sources, "exposures": exposures}


def _kind(row: dict) -> str:
    """Which names a row's column holds: an exposure's, a source's, or a model's (a seed's or snapshot's for a parent)."""
    if row["column_name"] == "exposure_name":
        return "exposures"
    return "sources" if row["fct_name"] == "fct_sources_without_freshness" else "nodes"


def _rows_matching_nothing(rows: list[dict], manifest: dict) -> list[str]:
    names = _resource_names(manifest)
    return [
        f"{row['fct_name']} {row['column_name']} {row['id_to_exclude']}"
        for row in rows
        if not any(_like(row["id_to_exclude"]).fullmatch(name) for name in names[_kind(row)])
    ]


def test_a_row_naming_a_mart_by_its_unversioned_name_matches_nothing_once_the_mart_is_versioned():
    """The four renamed rows of 2026-10-09, against a manifest in dbt 2.0.6's shape (a node per version, `version` an
    integer): `closures` names nothing once the mart is closures.v1, and `closures.v%` names it."""
    manifest = {
        "nodes": {
            "model.ourhike.closures.v1": {"resource_type": "model", "name": "closures", "version": 1},
            "model.ourhike.stg_octa__trail_lines": {"resource_type": "model", "name": "stg_octa__trail_lines"},
            "seed.ourhike.notice_readers": {"resource_type": "seed", "name": "notice_readers"},
        },
        "sources": {"source.ourhike.atc.raw_atc__water_distance": {"source_name": "atc", "name": "raw_atc__water_distance"}},
        "exposures": {"exposure.ourhike.step_form_route": {"name": "step_form_route"}},
    }
    rows = [
        {"fct_name": "fct_model_fanout", "column_name": "parent", "id_to_exclude": "closures"},
        {"fct_name": "fct_model_fanout", "column_name": "parent", "id_to_exclude": "closures.v%"},
        {"fct_name": "fct_too_many_joins", "column_name": "resource_name", "id_to_exclude": "stg_%__trail_lines"},
        {"fct_name": "fct_rejoining_of_upstream_concepts", "column_name": "parent", "id_to_exclude": "notice_readers"},
        {
            "fct_name": "fct_sources_without_freshness",
            "column_name": "resource_name",
            "id_to_exclude": "atc.raw_atc__water_distance",
        },
        {"fct_name": "fct_sources_without_freshness", "column_name": "resource_name", "id_to_exclude": "raw_atc__water_distance"},
        {"fct_name": "fct_exposures_dependent_on_private_models", "column_name": "exposure_name", "id_to_exclude": "step_%"},
        {"fct_name": "fct_hard_coded_references", "column_name": "model", "id_to_exclude": "step_form_route"},
    ]
    assert _rows_matching_nothing(rows, manifest) == [
        "fct_model_fanout parent closures",
        "fct_sources_without_freshness resource_name raw_atc__water_distance",
        "fct_hard_coded_references model step_form_route",
    ]
    assert _like("int_%unioned").fullmatch("int_closures__club_notices_part_1_unioned")
    assert not _like("closures").fullmatch("closures.v1")
    assert _like("a_c").fullmatch("abc"), "LIKE's `_` is any one character"


@pytest.fixture(scope="module")
def manifest(tmp_path_factory) -> dict:
    """The project as dbt parses it now, into a directory of its own."""
    root = tmp_path_factory.mktemp("exceptions_manifest")
    env = {
        **os.environ,
        "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
        "OURHIKE_WAREHOUSE": str(root / "warehouse.duckdb"),
        "OURHIKE_PROCESSED_DIR": str(root / "processed"),
    }
    completed = subprocess.run(
        [DBT, "parse", "--profiles-dir", ".", "--target-path", str(root / "target"), "--log-path", str(root / "logs")],
        cwd=DBT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    path = root / "target" / "manifest.json"
    assert completed.returncode == 0 and path.exists(), completed.stdout[-3000:] + completed.stderr[-2000:]
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")
def test_every_row_names_a_resource_the_project_has_under_its_current_name(manifest):
    dead = _rows_matching_nothing(_rows(), manifest)
    assert not dead, f"rows whose pattern names nothing the project has, so they suppress nothing yet: {dead}"
