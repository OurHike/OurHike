"""USGS — The National Map: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked the TNM dataset list (15) and the carto services.",),
    where=(
        "https://earthquake.usgs.gov/arcgis/rest/services",
        "https://partnerships.nationalmap.gov/arcgis/rest/services",
        "https://usgs.gov/",
    ),
)
