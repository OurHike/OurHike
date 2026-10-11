"""Nebraska Game and Parks Commission: points of interest (decision 122's held load, here since the commission's row;
closures.py says how this folder came to be).

- `ngpc_amenities`: `Amenities/FeatureServer/0`, 2,929 amenities at the commission's parks (2026-10-09), 382 of
  them 'Drinking Water' and 59 'Shelter'. Keyed on (AmenityID, DateCreated, the shape), the one unique set a live
  read found (its row's `key_comment`, 2026-10-11): its id, OBJECTID, is a server row id.

make_dbt_staging.py stages these points now that the steward has a folder of its own; no seeds/club_poi_types.csv row
types AmenityType yet, so none of them publishes until one does. Monthly.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ngpc_amenities",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
