"""A metric's definition cannot change silently (#1902, app/core/analytics_rollup.py).

Every month records the `DEFINITION_VERSION` it was computed under, so a
reader can tell a series that changed meaning from one that changed. That
only works if a change to what a metric counts actually bumps the version -
and "remember to bump it" is not a mechanism. This is: the metric SQL, the
close window and the User-table upsert are fingerprinted, and the
fingerprint is recorded per version.

When this fails, the question it is asking is whether what some metric
COUNTS changed. If yes, bump DEFINITION_VERSION and add the new fingerprint
under the new number - closed months keep the version they were closed
under. If only the wording of the SQL changed, replace the current line.
"""

import pytest

from app.core.analytics_rollup import DEFINITION_FINGERPRINTS, DEFINITION_VERSION, definition_fingerprint


def test_the_metric_sql_is_the_sql_this_definition_version_recorded():
    assert definition_fingerprint() == DEFINITION_FINGERPRINTS.get(DEFINITION_VERSION), (
        "The metric SQL in app/core/analytics_rollup.py changed. If what a metric counts "
        "changed, bump DEFINITION_VERSION and record the new fingerprint under it; if "
        f"only the wording changed, update version {DEFINITION_VERSION}'s line. "
        f"The fingerprint now is {definition_fingerprint()}."
    )


def test_every_version_up_to_the_current_one_is_on_the_ledger():
    assert sorted(DEFINITION_FINGERPRINTS) == list(range(1, DEFINITION_VERSION + 1))


@pytest.mark.parametrize(
    "module, name, changed",
    [
        ("app.core.analytics_rollup", "CLOSE_AFTER_DAYS", 21),
        ("app.core.analytics_rollup", "_MONTH_ROWS", "select count(*) from analytics_events where local_date >= :start"),
        ("app.routers.analytics", "_UPSERT_USER", "insert into analytics_users (user_key) values (:user_key)"),
    ],
    ids=["the-close-window", "the-rows-a-month-froze-with", "the-user-table-upsert"],
)
def test_what_decides_a_frozen_figure_is_part_of_the_definition(monkeypatch, module, name, changed):
    """A longer close window freezes a month with more of its rows, and the
    upsert is where hikers_new and every milestone come from: changing either
    changes what a stored number means as surely as the metric SQL does."""
    from importlib import import_module

    from sqlalchemy import text

    before = definition_fingerprint()
    monkeypatch.setattr(import_module(module), name, changed if isinstance(changed, int) else text(changed))

    assert definition_fingerprint() != before


def test_whitespace_alone_does_not_change_a_definition(monkeypatch):
    from sqlalchemy import text

    from app.core import analytics_rollup

    before = definition_fingerprint()
    reflowed = text("\n\n   ".join(str(analytics_rollup._HIKERS_NEW).split(" ")))
    monkeypatch.setattr(analytics_rollup, "_HIKERS_NEW", reflowed)

    assert definition_fingerprint() == before
