"""Nez Perce (Nee-Me-Poo) Trail Foundation: elevation, nothing published (coverage audit 2026-10-01,
batch c11_nht).

USGS 3DEP

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same checks",),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/CPCzfCPkoQSKO5TC/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://nezpercetrail.net/",
    ),
)
