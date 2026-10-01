"""The Mountains-to-Sea Trail as NC Commerce published it in 2020, `Mountains_to_Sea_Trail/0`.

328 lines, last edited 2020-10-19 (coverage audit 2026-10-01, batch
b7_long_trails_states). NC DPR's own `State_Trails/FeatureServer/1` holds
402 MST segments, last edited 2026-09-30, and is the current layer
(ORG_COVERAGE_SURVEY.md §3d); 120 of those are `Planned` and must not draw
as trail. Pointing `nc_mst_trail` at it is a reviewed registry change, not
made here.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nc_mst_trail",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
