"""Pacific Crest Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The Halfmile water and campsite points are a 2018 survey: as water they are stale by design, so
freshness labelling is mandatory. Halfmile's own terms are @unvalidated; what would settle them is
PCTA or Halfmile saying whether CC BY reaches these layers.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Trailheads_Current/FeatureServer/0`: 487 points, last edit 2026-09-01, with `amenities_bathroom`, "
        "`parking_` and `external_trailheadManager`. `PCT_Mile_Markers_2026/FeatureServer/0`: 5,320, last edit "
        "2026-01-07. `Mountain_Passes/FeatureServer/0`: 128. `Halfmile_Point_2018/FeatureServer/5` Water_Source"
        " 1,159; `/16` Campsite 442; `/6` Trail_Junctions 656; `/8` Road_Crossing 467; `/4` Gate 73. All "
        "Halfmile layers last edited 2021-02-24.",
    ),
    where=(
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Trailheads_Current/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCT_Mile_Markers_2026/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Mountain_Passes/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Halfmile_Point_2018/FeatureServer/5",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
