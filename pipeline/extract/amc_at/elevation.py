"""Appalachian Mountain Club (A.T. sections): elevation, nothing published (coverage audit 2026-10-01,
batch c1_at_clubs_north).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Only an `ELEV` attribute on `AMC_Destinations`. No DEM or profile product appears on the site nav or "
        "the ArcGIS account.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services",
        "https://outdoors.org/",
    ),
)
