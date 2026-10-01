"""Chesapeake Conservancy: elevation, nothing published (coverage audit 2026-10-01, batch c11_nht).

USGS 3DEP

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Checked: the cicgis folder list (61 folders). Only project contours (`douglaspoint_contour_4m`), not a trail product",
    ),
    where=(
        "https://cicgis.org/arcgis/rest/services",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://chesapeakeconservancy.org/",
    ),
)
