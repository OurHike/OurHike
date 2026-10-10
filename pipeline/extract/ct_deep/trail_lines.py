"""CT DEEP's blue-blazed hiking trails, `BlueBlazedHikingTrails/0`.

351 lines, last edited 2024-05-17 (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa). CFPA's `BBHT_Public_Map_Trails`, edited 2026-09-29, is
the steward's current layer (ORG_COVERAGE_SURVEY.md §3d). Not landed: DEEP's
`DEEP_Trails_Set/FeatureServer/3`, 13,883 polylines in 124 trail systems,
CC0, last edited 2026-09-17; a loader must drop its `TRAILSTAT` Potential and
Committed rows and the motorized ones. This layer's `Gains` and `Losses`
columns land with it, which is why not_available.toml [ct_deep.elevation] shares it.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ct_deep_blue_blazed",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
