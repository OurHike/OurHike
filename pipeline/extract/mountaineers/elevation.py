"""The Mountaineers: elevation, could not be told (coverage audit 2026-10-01, batch c5_regional_2).

USGS 3DEP for the data.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Cloudflare challenge.",),
    where=(
        "https://services9.arcgis.com/fUZ4ZUl57GG2z81p/arcgis/rest/services",
        "https://mountaineers.org/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
