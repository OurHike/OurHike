"""Wisconsin DNR Open Data: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Daily fire danger is the hourly or daily lane's, not the monthly one (decision 1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`FR_WIS_BURN/FR_WIS_BURN_MAP_EXT/MapServer/13` "Current Fire Danger": 72 county polygons with '
        "`DANGER_RATING_NAME`, `NO_BURN_FLAG`, `PERMIT_RESTRICTIONS`. Newest `LAST_CHANGED_DATE` is 2026-09-30 "
        "11:53 UTC; all 72 read LOW today. `/0` Wildfires (Today) holds 0 rows.",
    ),
    where=("https://dnrmaps.wi.gov/arcgis/rest/services/FR_WIS_BURN/FR_WIS_BURN_MAP_EXT/MapServer/13",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
