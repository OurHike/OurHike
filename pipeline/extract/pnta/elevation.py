"""Pacific Northwest Trail Association: elevation, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same places checked.",),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services",
        "https://pnt.org/",
    ),
)
