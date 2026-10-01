"""Lone Star Hiking Trail Club: elevation, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

USGS 3DEP covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The maps page offers USGS-topo PDFs and no profile product.",),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://lonestartrail.org/",
    ),
)
