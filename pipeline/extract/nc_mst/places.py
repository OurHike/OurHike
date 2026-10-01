"""NC Mountains-to-Sea Trail (state-published layer): places, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NC_State_Parks_System/0` ParkBoundaries: 346 polygons (`PK_NAME`, `PK_TYPE`), last edit 2026-09-30. "
        "Also `State_Owned_Land_(Latest)`.",
    ),
    where=(
        "https://services.nconemap.gov/secure/rest/services",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
        "https://trails.nc.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
