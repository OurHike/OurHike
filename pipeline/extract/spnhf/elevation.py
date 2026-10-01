"""Society for the Protection of NH Forests: elevation, nothing published (coverage audit 2026-10-01,
batch c4_regional_1).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked the nav and sitemap.",),
    where=(
        "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services",
        "https://forestsociety.org/",
    ),
)
