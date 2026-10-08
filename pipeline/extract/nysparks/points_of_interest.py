"""NY State Parks' points of interest: its park facilities, and the Empire State Trail's own features.

- `oprhp_facilities`: OPRHP's park facilities, `NY_State_Park_Facilities/FeatureServer/0`. 8,823
  points, last edited 2026-08-12 (coverage audit 2026-10-01, batch b4_oprhp_mohonk_gatc). The 136
  Water Spigot and 15 Drinking Fountain rows land with the rest: sources.json's
  `oprhp_water_holdback` keeps them off a phone, and it is applied downstream of this extract,
  which never filters on it.
- `oprhp_est_trail_features`: the Empire State Trail's parking areas, campgrounds, restrooms and
  train stations, `EST_Public/FeatureServer/1` (TrailFeature), 381 points, read live 2026-10-08
  for decision 54's wave 6. The Empire State Trail was a candidate steward of its own in the
  coverage audit (`empire-state-trail`), which folds it into this folder: the trail is OPRHP's,
  and the service is on OPRHP's ArcGIS organisation beside the other layers here. Its
  PhoneNumber and Address are never asked for (its sources.json row says why).

Each layer's row in sources.json holds its counts, dates, terms and key. Change checks are
_kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS Online, and an allowed
zero only beside the server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_facilities", "oprhp_est_trail_features")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
