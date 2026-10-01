"""Alaska Trails: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

These are planning records (they carry a `Cost` field), but "impassable crossing" is a hazard point
all the same.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`AKLT_Trail_Obstacles/FeatureServer/20`: 13 points, last edit 2026-03-05: `BridgeNeeded(Impassable)` "
        "4, `BridgeNeeded(Passable)` 7, `RiverFord` 2. `Seward_to_Eagle_River_Obstacles/2`: 7 (2023-05-17).",
    ),
    where=("https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/AKLT_Trail_Obstacles/FeatureServer/20",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
