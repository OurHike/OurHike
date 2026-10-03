"""Lewis & Clark Trail Heritage Foundation: elevation, nothing published (coverage audit 2026-10-01,
batch c11_nht).

USGS 3DEP

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked: WP REST pages, posts, search",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://lewisandclark.org/",
    ),
)
