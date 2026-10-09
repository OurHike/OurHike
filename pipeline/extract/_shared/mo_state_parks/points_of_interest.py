"""Missouri State Parks: points of interest, held (decision 122; see closures.py beside this file).

- `mo_state_parks_trail_pois`: `sphs_trails/SPHS_trails_public/MapServer/2`, 4,018 trail points statewide
  (2026-10-09), among them 21 water fountains and 3 backpack camping shelters (PNT_TYPE).

Raw only: make_dbt_staging.py stages club folders, so these points reach no model until the steward has a folder
of its own and seeds/club_poi_types.csv types its values. Monthly, the type's default lane.
"""

from extract._kinds import arcgis_layer

TYPE = "points_of_interest"
CLAIMS = ("mo_state_parks_trail_pois",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
