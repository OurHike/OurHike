"""The public page's database size against the backend's own, so that two readings of one size cannot drift apart.

The maintainer's poll of 2026-10-28 on #1902 — Count six usage events with a
sealed account id and GPS fix, keep them six months, close each month into a
table, and report them per club ("Hourly dbt check, with megabytes") put the
whole database's size on the public data-quality page, read hourly by the
pipeline, beside this backend's nightly `database_near_quota` check and the
private report's storage strip. So one size is read in two places, and this
holds them to one query, one megabyte and one warning line:

- pipeline/lib/database_size.py's DATABASE_SIZE_SQL is the text of
  app/core/analytics_storage.py's `_DATABASE_BYTES`, and its MEGABYTE is `_MB`;
- dbt's base model rounds bytes down by that same megabyte, so a size of
  400 there is 400 · `_MB` bytes or more;
- dbt's test warns from STORAGE_WARN_SHARE of `database_quota_mb`, 400 of
  500, which `share >= STORAGE_WARN_SHARE` on bytes reaches at exactly the
  same byte (Reasoned: floor(bytes / MB) >= 400 exactly when bytes >= 400 MB),
  and fails from 95% of the quota, the line the same poll chose. A paid plan
  that raises `database_quota_mb` fails this until the test's lines move too.

The pipeline is read as text, as test_conditions_publisher_contract.py reads
the conditions publisher, because it is not importable from here (its own
package and dependencies). What this cannot hold: that the conditions reader
and the rollup's role may connect to the same databases, which
lib/database_size.py names as @unvalidated.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.config import settings
from app.core import analytics_storage
from app.core.analytics_quality import STORAGE_WARN_SHARE

REPO_ROOT = Path(__file__).resolve().parents[2]
SIZE_MODULE = REPO_ROOT / "pipeline" / "lib" / "database_size.py"
BASE_MODEL = REPO_ROOT / "pipeline" / "dbt" / "models" / "staging" / "ourhike" / "base" / "base_ourhike__database_size.sql"
SIZE_TEST = REPO_ROOT / "pipeline" / "dbt" / "tests" / "singular" / "assert_the_database_stays_under_its_plan.sql"
# Declared as a set so tests/test_ci_scope.py can hold the workflow's scope list to it.
PIPELINE_FILES_READ = {SIZE_MODULE, BASE_MODEL, SIZE_TEST}

#: The share of the quota the test fails from: the poll's 95%.
FAIL_SHARE = 0.95


def _constants() -> dict[str, ast.expr]:
    """lib/database_size.py's top-level assignments, by name, unevaluated."""
    tree = ast.parse(SIZE_MODULE.read_text())
    return {
        node.targets[0].id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
    }


def _whole(node: ast.expr) -> int:
    """A constant written as an int or a product of ints, which is how MEGABYTE is written."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _whole(node.left) * _whole(node.right)
    raise AssertionError(f"{ast.unparse(node)} is not a whole number written as one or as a product")


def _threshold(name: str) -> int:
    """The N of the size test's `warn_if` or `error_if`, written `>N`, as every test in the project declares one."""
    match = re.search(rf"\b{name}\s*=\s*'>(\d+)'", SIZE_TEST.read_text())
    assert match, f"no {name}='>N' in {SIZE_TEST.name}: if the test moved, fix this one rather than deleting it"
    return int(match.group(1))


def test_the_pipelines_size_query_is_the_backends_text_whole():
    sql = _constants().get("DATABASE_SIZE_SQL")
    assert isinstance(sql, ast.Constant) and isinstance(sql.value, str), "lib/database_size.py lost DATABASE_SIZE_SQL"
    assert sql.value == analytics_storage._DATABASE_BYTES.text


def test_a_megabyte_is_the_same_number_of_bytes_in_the_backend_the_pipeline_and_the_base_model():
    assert _whole(_constants()["MEGABYTE"]) == analytics_storage._MB == 1024 * 1024
    assert f"floor(database_bytes / {analytics_storage._MB})" in BASE_MODEL.read_text()


def test_the_public_check_warns_at_the_backends_line_and_fails_at_95_percent_of_the_quota():
    """`>N` warns from N + 1, the size being whole megabytes."""
    warns_from, fails_from = _threshold("warn_if") + 1, _threshold("error_if") + 1
    assert warns_from == round(STORAGE_WARN_SHARE * settings.database_quota_mb) == 400
    assert fails_from == round(FAIL_SHARE * settings.database_quota_mb) == 475
    assert warns_from < fails_from < settings.database_quota_mb
