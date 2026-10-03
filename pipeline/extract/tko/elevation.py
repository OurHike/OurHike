"""Trailkeepers of Oregon: elevation, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Trailhead pages carry one elevation each. There is no profile or DEM.",),
    where=(
        "https://services3.arcgis.com/3g7oRa9lIIf3eCBb/arcgis/rest/services",
        "https://trailkeepersoforegon.org/",
    ),
)
