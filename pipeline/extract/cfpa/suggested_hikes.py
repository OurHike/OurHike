"""Connecticut Forest & Park Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Page. Trail descriptions rather than routed hikes. Skeptic spot-check: `/trails/appalachian-trail/`
returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`https://ctwoodlands.org/trails/`: 57 trail pages with mileage, e.g. `/trails/appalachian-trail/` (56.6 mi).",),
    where=(
        "https://ctwoodlands.org/trails/",
        "https://ctwoodlands.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
