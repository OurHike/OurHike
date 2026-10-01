"""Colorado Parks & Wildlife — COTREX: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Under the COTREX terms this is page-only until CPW says otherwise.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Format page: `trails.colorado.gov/featured-routes` (8 `/routes/<id>` links on the page).",),
    where=(
        "https://trails.colorado.gov/featured-routes",
        "https://trails.colorado.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
