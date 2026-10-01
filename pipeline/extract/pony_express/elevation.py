"""National Pony Express Association: elevation, nothing published (coverage audit 2026-10-01, batch
c11_nht).

USGS 3DEP

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked: 57 WP pages via REST (only `wp/v2` namespace), FAQ, maps page",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nationalponyexpress.org/",
    ),
)
