"""NorthEast Texas Trail Coalition: points of interest (decision 122's held load, here since the coalition's row;
closures.py says how this folder came to be).

- `nett_trail_pois`: `NET_Trail/FeatureServer/0`, 167 trail features typed by a coded domain (2026-10-09): 2 water
  fountains, 7 restrooms and 44 trailheads among them. 8 of the 167 lie outside north-east Texas, reaching lon
  -117.20 (every point read 2026-10-11), which its row says must never be drawn on this trail.

make_dbt_staging.py stages these points now that the steward has a folder of its own; no seeds/club_poi_types.csv row
types its codes yet, so none of them publishes until one does, and the 8 outliers need a seeds/layer_rules.csv hold
before any is typed. Monthly.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nett_trail_pois",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
