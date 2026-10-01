"""Mid State Trail Association (PA): elevation, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'ArcGIS "Mid State Trail Elevation Profiler" (2017) is an Esri Profile app, "For educational purposes '
        'only". It is a viewer, not a dataset.',
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services",
        "https://hike-mst.org/",
    ),
)
