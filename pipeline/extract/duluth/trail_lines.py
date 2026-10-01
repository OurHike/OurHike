"""The City of Duluth's Superior Hiking Trail, `TrailsDuluthService/MapServer/0`.

67 lines (coverage audit 2026-10-01, batch b7_long_trails_states), about 100
mi of a 300.3-mi trail whose whole is in NCTA's `agol_sht_public`
(ORG_COVERAGE_SURVEY.md §3c). Not landed: layer 14, "Trails - All City",
801 lines, which contains these 67.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("duluth_superior_hiking_trail",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
