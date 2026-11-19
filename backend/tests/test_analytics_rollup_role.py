"""The rollup role's column grant names every usage column but `sealed`.

`ourhike_analytics_rollup` reads `analytics_events` column by column, through
the GRANT in features/EVENTING.md §0 ("The rollup's role"), so that the one
scheduled job holding a production credential for usage data cannot read a
sealed position or account. The price of a column-by-column grant is that a
column added later is one the role cannot read: the nightly rollup then fails
in production with "permission denied" on a query every test here passed,
because the tests connect as the table's owner. #1885's `support_cents` was
the first column to meet that; its migration grants it to a role that already
exists, and this test keeps the documented SQL - which makes the role on a
new database - in step with the table.
"""

import re
from pathlib import Path

from app.models.analytics import AnalyticsEvent

EVENTING = Path(__file__).resolve().parents[2] / "features" / "EVENTING.md"

# Read by tests/test_ci_scope.py, which fails if backend-tests.yml's scope list
# stops naming this file - a docs-only pull request is the one that drifts.
DOCS_FILES_READ = (EVENTING,)

# The one column the role must never read.
WITHHELD = {"sealed"}


def _granted_columns() -> set[str]:
    assert EVENTING.exists(), f"{EVENTING} is missing, so the grant cannot be checked"
    grant = re.search(
        r"GRANT SELECT \(([^)]*)\)\s+ON public\.analytics_events TO ourhike_analytics_rollup",
        EVENTING.read_text(encoding="utf-8"),
    )
    assert grant is not None, "the rollup role's GRANT SELECT on analytics_events is not where this test reads it"
    return {column.strip() for column in grant.group(1).split(",")}


def test_the_rollup_role_is_granted_every_usage_column_but_the_sealed_one():
    table = {column.name for column in AnalyticsEvent.__table__.columns}

    assert _granted_columns() == table - WITHHELD


def test_the_sealed_column_is_never_granted():
    assert not (_granted_columns() & WITHHELD)
