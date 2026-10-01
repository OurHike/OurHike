"""Black Hills Trails: elevation, nothing published (coverage audit 2026-10-01, batch c5_regional_2).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Trail pages.",),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services3.arcgis.com/NbEEwwcVRO4AIaWE/arcgis/rest/services",
        "https://blackhillstrails.org/",
    ),
)
