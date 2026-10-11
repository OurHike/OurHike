"""New York State Canal Corporation: points of interest (decision 122's held load, here since the Canal Corporation's
row; closures.py says how this folder came to be).

- `nys_canal_water_fountains`: `Erie_WaterFountains/FeatureServer/48`, the Erie Canalway Trail's 2 water
  fountains from a 2022 field survey: a survey's count, not a census of water on the trail.

The survey's other amenity layers (Erie_Bathroom, Erie_Pavilion, Erie_TrailAccessPoint and more) wait for the rest
of the Canal Corporation's layers. make_dbt_staging.py stages these points now that the steward has a folder of its
own; no seeds/club_poi_types.csv row types them yet, so neither publishes until one does. Monthly.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nys_canal_water_fountains",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
