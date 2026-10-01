"""Alaska Trails: places, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`AKLT_POI/FeatureServer/78`: 42 (Community 26, Local 8, Places 8). "
        "`ALT_Recreation_LandOwnership_and_Boundaries/0`: 4,476 polygons, a copy of the BLM's data that goes to"
        " `_shared/blm`.",
        "Skeptic adds: `Story_Map_Pins/FeatureServer/0`: 36 (Community 15, Subsection Point 11, Local Point 9, "
        "Major Section Point 1), with `DisplayTitle`, `Description` and `Route_Name`, last edit 2026-04-20. "
        'There are five regional `_Story_Map_Pins` services as well. The web map "Alaska Long Trail - Weather '
        "Watch and Warnings\" (2026-03-23) draws Esri's live NWS feed, so it is `_shared/` weather, not a club "
        "warning …",
    ),
    where=(
        "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/AKLT_POI/FeatureServer/78",
        "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/Story_Map_Pins/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
