"""Wasatch Mountain Club: photos, nothing published (coverage audit 2026-10-01, batch c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/photo-albums` holds members' photos with no licence.",),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://wasatchmountainclub.org/",
    ),
)
