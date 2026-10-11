"""Missouri State Parks: points of interest (decision 122's held load, here since the steward's row; closures.py says
how this folder came to be).

- `mo_state_parks_trail_pois`: `sphs_trails/SPHS_trails_public/MapServer/2`, 4,018 trail points statewide
  (2026-10-09), among them 21 water fountains and 3 backpack camping shelters (PNT_TYPE).

make_dbt_staging.py stages these points now that the steward has a folder of its own. No seeds/club_poi_types.csv row
types PNT_TYPE yet, and int_points_of_interest__club_points reads that seed as an allowlist, so none of them publishes
until one does. Monthly, the type's default lane.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("mo_state_parks_trail_pois",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
