"""Standing Stone Trail Club: places, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "34 maintenance sections with named endpoints and lengths (`/trail-sections`). Two trail towns in the "
        "Sweet 16 (Three Springs, Mapleton Depot). Termini on `/trail-guides`.",
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
