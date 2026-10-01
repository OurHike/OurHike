"""Nez Perce (Nee-Me-Poo) Trail Foundation: podcasts, nothing published (coverage audit 2026-10-01,
batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Checked as above. One YouTube link ("A Landscape of History") is video',),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/CPCzfCPkoQSKO5TC/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://nezpercetrail.net/",
    ),
)
