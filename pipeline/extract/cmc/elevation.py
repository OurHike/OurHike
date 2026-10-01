"""Carolina Mountain Club: elevation, nothing published (coverage audit 2026-10-01, batch
c3_at_clubs_south).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Only the per-hike "Total Elevation Gain (Feet)" on find-a-hike detail pages.',),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://carolinamountainclub.org/",
    ),
)
