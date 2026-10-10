"""Nebraska Game and Parks Commission: points of interest, held (decision 122; see closures.py beside this file).

- `ngpc_amenities`: `Amenities/FeatureServer/0`, 2,929 amenities at the commission's parks (2026-10-09), 382 of
  them 'Drinking Water' and 59 'Shelter'.

Raw only until the steward has a folder of its own and seeds/club_poi_types.csv types its values. Monthly.
"""

from extract._kinds import arcgis_layer

TYPE = "points_of_interest"
CLAIMS = ("ngpc_amenities",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
