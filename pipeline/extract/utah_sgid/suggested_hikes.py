"""Utah UGRC — SGID Trails and Pathways: suggested hikes, nothing published (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`gis.utah.gov` homepage and a keyword scan of the 904 services: no hike product.",),
    where=(
        "https://gis.utah.gov",
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
    ),
)
