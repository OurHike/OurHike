"""Bartram Trail Conference: elevation, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

USGS 3DEP covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The section prose gives spot heights ("Sandy Ford Road (1,625 feet) … Rainy Mountain (2,936 feet)"). '
        "That is not a product.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services",
        "https://bartramtrail.org/",
    ),
)
