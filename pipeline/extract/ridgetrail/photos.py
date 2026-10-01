"""Bay Area Ridge Trail Council: photos, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Section pages show photos credited "via AllTrails" to individuals, with no licence.',),
    where=(
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services",
        "https://ridgetrail.org/",
    ),
)
