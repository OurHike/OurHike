"""PCTA's centerline, `PCTA_Centerline/FeatureServer/0`.

1 line, last edited 2026-01-06, `hasZ` false (coverage audit 2026-10-01,
batch b7_long_trails_states). Not landed: `PCT_Side_Trails/FeatureServer/0`,
1,003 lines, the water and resupply spurs.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("pcta_centerline",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
