"""The conditions publisher's column lists, against this backend's schemas.

`pipeline/export_conditions.py` bakes `closures.json` and `reports.json`
artifacts a hiker reads as the baseline when the backend is unreachable, with
hand-written SQL whose column lists deliberately mirror `ClosureOut` and the
anonymous slice of `ReportOut` (#433 made the closures shapes match so the
client can overlay a live read on the baseline without a conversion). Nothing
enforced the mirror (#446): the publisher is a third party to the
backend↔client contract #316 covers, so a column renamed in the model got a
passing backend suite, a passing pipeline suite (whose own test DDL mirrors
the model by hand), and a failing nightly publish at 08:40 UTC - seen by
whoever reads the tracking issue, not by whoever renamed the column.

This is that enforcement, in the pattern TESTING.md's Redundancy section
names for cross-part contracts: read the other end's source as text, compare
against the OpenAPI document this app actually serves, and guard the parse
itself so a regex that matches nothing can never pass as agreement. It lives
in the backend suite because the OpenAPI document lives here; the workflow's
scope list names `pipeline/export_conditions.py` so a pipeline-side edit
still triggers this suite (see tests/test_ci_scope.py).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]

# Read as text, the way the client-contract tests read client source: the
# pipeline is not importable from here (different package, its own
# dependencies), and text is all this comparison needs. Declared as a set so
# tests/test_ci_scope.py can hold the workflow's scope list to it.
PIPELINE_FILES_READ = {REPO_ROOT / "pipeline" / "export_conditions.py"}

EXPORT_CONDITIONS = next(iter(PIPELINE_FILES_READ))


def _sql_constant(name: str) -> str:
    source = EXPORT_CONDITIONS.read_text()
    match = re.search(rf'{name} = """(.*?)"""', source, re.DOTALL)
    assert match, (
        f"{name} not found in {EXPORT_CONDITIONS}. If the publisher's SQL "
        "moved or was renamed, fix this test rather than deleting it - it is "
        "what catches a closures column renamed out from under the publisher."
    )
    return match.group(1)


def _selected_columns(sql: str) -> set[str]:
    select_list = re.search(r"SELECT(.*?)FROM", sql, re.DOTALL)
    assert select_list, f"no SELECT ... FROM in:\n{sql}"
    return {column.strip().strip('"') for column in select_list.group(1).split(",")}


def _schema_properties(name: str) -> set[str]:
    return set(app.openapi()["components"]["schemas"][name]["properties"])


def test_the_closures_artifact_selects_exactly_what_closureout_serves():
    """Equality in both directions, because #433 made the shapes match
    deliberately: a column the SQL selects and the schema dropped is a rename
    arriving from the backend side, and a field the schema grew that the SQL
    does not select is a baseline quietly narrower than the live overlay."""
    assert _selected_columns(_sql_constant("PUBLIC_CLOSURES_SQL")) == _schema_properties("ClosureOut")


def test_the_reports_artifact_selects_a_subset_of_reportout():
    """Subset, in one direction, for the reason the publisher's own header
    gives: the artifact tracks what `ReportOut.for_viewer` sends an ANONYMOUS
    caller, so the withheld fields (reporter_id, received_at, maintainer_id,
    club_id) are never selected at all rather than published as nulls."""
    selected = _selected_columns(_sql_constant("PUBLIC_REPORTS_SQL"))

    assert selected <= _schema_properties("ReportOut"), (
        "the reports artifact selects columns ReportOut does not serve - a "
        f"rename has split the two: {sorted(selected - _schema_properties('ReportOut'))}"
    )


def test_the_reports_artifact_still_omits_photo_url():
    """#436's decision, pinned: the live endpoint answers photos with a
    short-lived presigned URL, so a baked artifact publishing one would be
    broken by the time it was read. Deliberate omission, not drift."""
    assert "photo_url" not in _selected_columns(_sql_constant("PUBLIC_REPORTS_SQL"))


def test_this_is_actually_comparing_column_lists():
    """Guards the guard: a parse that returned nothing would make the subset
    test above pass vacuously and the equality test compare empty sets."""
    assert len(_selected_columns(_sql_constant("PUBLIC_CLOSURES_SQL"))) >= 10
    assert len(_selected_columns(_sql_constant("PUBLIC_REPORTS_SQL"))) >= 10
    assert len(_schema_properties("ClosureOut")) >= 10
