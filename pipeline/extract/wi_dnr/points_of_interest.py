"""Wisconsin DNR Open Data: points of interest, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`services5.arcgis.com/Ul9AyFFeFTjf08DW/.../Fire_Towers_(VIEW_ONLY)/0`: 98 fire towers, last edit "
        "2025-10-22. `WIParks_V2_PUBLIC_VIEW/0`: 133 property points with `Camping`, `Hiking` flags, last edit "
        "2026-09-24. No campsite or shelter layer in the 282 hosted services or the `LF_DML` folder.",
    ),
    where=("https://dnrmaps.wi.gov/arcgis/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
