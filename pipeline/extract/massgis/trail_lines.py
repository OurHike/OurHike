"""MassGIS's long-distance trails, `AGOL/Long_Distance_Trails/MapServer/0`.

32 lines under 7 names, no `editingInfo` (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa). The steward is DCR, and the lines are compiled from club
GPS tracks (ORG_COVERAGE_SURVEY.md §3b). Not landed:
`AGOL/DCR_Roads_and_Trails_Arcs/MapServer/0` (36,859 arcs, 6,764 of them
public roads) and `AGOL/Map_Trails_Pub_True/FeatureServer/0` (9,553 trail
segments compiled by the regional planning agencies).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("massgis_long_distance_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
