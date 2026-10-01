"""USGS — The National Map: places, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "GNIS `geonames/MapServer` (Populated Places, Landforms); `govunits/MapServer`; National Boundary "
        "Dataset via TNM Access.",
    ),
    where=(
        "https://earthquake.usgs.gov/arcgis/rest/services",
        "https://partnerships.nationalmap.gov/arcgis/rest/services",
        "https://usgs.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
