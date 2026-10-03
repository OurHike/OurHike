"""Colorado Trail Foundation: photos, could not be told (coverage audit 2026-10-01, batch
c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Site 403.",),
    where=(
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
        "https://coloradotrail.org/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
