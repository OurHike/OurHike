"""New York State Canal Corporation: points of interest, held (decision 122; see closures.py beside this file).

- `nys_canal_water_fountains`: `Erie_WaterFountains/FeatureServer/48`, the Erie Canalway Trail's 2 water
  fountains from a 2022 field survey: a survey's count, not a census of water on the trail.

The survey's other amenity layers (Erie_Bathroom, Erie_Pavilion, Erie_TrailAccessPoint and more) wait for the rest
of the Canal Corporation's layers. Raw only until the steward has a folder of its own. Monthly.
"""

from extract._kinds import arcgis_layer

TYPE = "points_of_interest"
CLAIMS = ("nys_canal_water_fountains",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
