"""City of Duluth Open Data: places, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`ParkBoundaryService/MapServer/0` Parks: 165 polygons (`PARK_NAME`, `PARK_TYPE`, `ACRES`); item modified 2026-02-19.",
    ),
    where=("https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
