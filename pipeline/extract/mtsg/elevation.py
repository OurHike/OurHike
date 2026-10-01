"""Mountains to Sound Greenway Trust: elevation, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

USGS 3DEP is the source.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav, page sitemap, ArcGIS owner listing (122 items).",),
    where=(
        "https://gis.dnr.wa.gov/site3/rest/services",
        "https://services.arcgis.com/b2nA3bRpH9jJyZOr/arcgis/rest/services",
        "https://mtsgreenway.org/",
    ),
)
