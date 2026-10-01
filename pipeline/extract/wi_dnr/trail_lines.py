"""WDNR's Ice Age Trail, `LF_DNR_REC_OPPS_WTM_Ext/MapServer/2`: 1 line, 711 mi.

Coverage audit 2026-10-01, batch b7_long_trails_states. The layer's own item
says it is updated about every two months and points to the Ice Age Trail
Alliance for more current data, which settles #1709 — Register the steward
and the redistributor both, and declare which one wins where they overlap
for this pair: IATA wins, on the redistributor's own words. Not landed:
layer 1, 219 state-trail segments.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wi_ice_age_trail",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
