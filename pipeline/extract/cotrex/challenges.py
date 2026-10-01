"""Colorado Parks & Wildlife — COTREX: challenges, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The COTREX terms caveat applies.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page. The CPW Passport Program covers 42 state parks and 15 hatcheries, with a patch (from "
        "search). `trails.colorado.gov/challenges` lists 13 COTREX citizen-science challenges "
        "(`drinking-water`, `conditions-report`, `butterfly`, …).",
    ),
    where=("https://trails.colorado.gov/challenges",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
