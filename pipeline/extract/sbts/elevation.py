"""Sierra Buttes Trail Stewardship: elevation, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav, sitemap, the 70-item ArcGIS owner listing.",),
    where=(
        "https://services6.arcgis.com/t5asxkRF7xoBwgqv/arcgis/rest/services",
        "https://sierratrails.org/",
    ),
)
