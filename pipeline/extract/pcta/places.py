"""Pacific Crest Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Permit areas tell a hiker where an unpermitted night is a citation. The sheriff polygons answer "who
do I call from here", which is the get-off-the-trail case.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Trail_Town_Resupply_Public/FeatureServer/0`: 106 trail towns, last edit 2025-05-12. "
        "`PCT_Letter_Sections/FeatureServer/0`: 29 sections. `PCTA_Centerline_Regions`: 6. "
        "`Permit_Areas_Public/FeatureServer/0`: 32 polygons with `Permit_required_on_PCT__Y_N`, `Quota` and "
        "`Permit_situation_summary`, last edit 2025-08-26. `WildernessAreasPCTA/FeatureServer/0`: 253 polygons.",
        "Skeptic adds: `PCT_Sheriffs_Offices/FeatureServer/0`: 45 county polygons with `Sheriff_Dept`, `Phone`,"
        " `Website`, last edit 2024-03-15.",
    ),
    where=(
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Trail_Town_Resupply_Public/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCT_Letter_Sections/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Permit_Areas_Public/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/WildernessAreasPCTA/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCT_Sheriffs_Offices/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
