"""Washington RCO's State Trails Database, `WA_RCO_Trails_Database_Public_View/FeatureServer/0`.

22,454 lines, last edited 2026-04-22 (coverage audit 2026-10-01, batch
b7_long_trails_states). Its `segment_length_mi` reads about 1.46 times
WSPRC's own mileage on four trails (ORG_COVERAGE_SURVEY.md §3b).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wa_rco_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
