"""Mid State Trail Association (PA): photos, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("No licensed collection.",),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services",
        "https://hike-mst.org/",
    ),
)
