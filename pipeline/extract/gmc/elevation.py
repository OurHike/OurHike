"""Green Mountain Club: elevation, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

USGS 3DEP. VCGI is a `_shared` lead, not a GMC file.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'No DEM or profile dataset. There is a Web Experience app "LT Elevation Profiles Builder" '
        '(`bed38ca4431a4e5ab0d0d6c42edd1463`), and the point layers carry `Elev_ft`. The "Long Trail Public '
        "Map\" draws VCGI's 100-ft contours "
        "(`maps.vcgi.vermont.gov/…/OPENDATA_VCGI_ELEVATION_SP_NOCACHE_v1/MapServer/6`), which are Vermont's, "
        "not GMC's.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services8.arcgis.com/kClE0vHJkIEmhQ53/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://greenmountainclub.org/",
    ),
)
