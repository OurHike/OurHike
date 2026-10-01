"""USGS — The National Map: closures, nothing published (coverage audit 2026-10-01, batch p09_persist).

USGS manages no recreation land (Reasoned). Closures belong to the land managers whose trails TNM
aggregates, keyed by `sourceoriginator`. The numeric `seasonopen` codes are undocumented and must
not be read as open or closed (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Tried: (1) walked 6 TNM ArcGIS hosts, the `/arcgis/rest/services` roots of partnerships, carto, index,"
        " basemap, hydro and elevation `.nationalmap.gov`: 47 services, none closure-, alert- or status-shaped."
        ' `USGSTrails/MapServer/0`\'s only status-like field is `seasonopen`, grouped today: null 554,257; "No" '
        '27,506; "Unknown" 23,691; "Yes" 1,165; "3" 431; "1" 117; "2" 32; "N" 2; "Other" 1. (2) AGOL "USGS '
        'National Map trail closure" (31) and "National Digital Trails closure status" (20) gave no USGS item. '
        '(5) data.gov "USGS trail closures" 0.',
    ),
    where=(
        "https://partnerships.nationalmap.gov/arcgis/rest/services/USGSTrails/MapServer/0",
        "https://data.gov",
        "https://usgs.gov/",
    ),
)
