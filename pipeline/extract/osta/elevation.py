"""Old Spanish Trail Association: elevation, could not be told (coverage audit 2026-10-01, batch
c11_nht).

USGS 3DEP

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Site walled",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://oldspanishtrail.org/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
