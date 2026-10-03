"""Natchez Trace NST (NPS-administered): elevation, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("NPS publishes no elevation product (c9's directory check).",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/natr/",
    ),
)
