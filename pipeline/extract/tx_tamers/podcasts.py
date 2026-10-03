"""Texas Trail Tamers: podcasts, nothing published (coverage audit 2026-10-01, batch c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same nav.",
        'Skeptic: the Apple directory for "Texas Trail Tamers" returns 8 unrelated shows.',
    ),
    where=(
        "https://services1.arcgis.com/1mtXwieMId59thmg/arcgis/rest/services",
        "https://tpwd.texas.gov/arcgis/rest/services",
        "https://texastrailtamers.org/",
    ),
)
