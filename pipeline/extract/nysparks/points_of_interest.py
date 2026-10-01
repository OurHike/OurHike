"""OPRHP's park facilities, `NY_State_Park_Facilities/FeatureServer/0`.

8,823 points, last edited 2026-08-12 (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc). The 136 Water Spigot and 15 Drinking Fountain rows land
with the rest: sources.json's `oprhp_water_holdback` keeps them off a phone,
and it is applied by the exporter, downstream of this extract, which never
filters on it. Not landed: `EST_Public/1` `TrailFeature`, 381 points along the
Empire State Trail.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_facilities",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
