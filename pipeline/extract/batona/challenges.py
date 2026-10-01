"""Batona Hiking Club: challenges, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/page-1652370`: "Batona Trail and BATONA Hiking Club patches are $3.00 each". That is a sale, with no'
        " completion requirement stated.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://batonahikingclub.org/",
    ),
)
