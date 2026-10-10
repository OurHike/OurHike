"""AZGeo Data Hub: places, extracted (decision 54, wave 1; live read 2026-10-03 under lib/user_agent.py's
USER_AGENT).

- `azt_gateway_communities`: Arizona Trail gateway communities, 22 point features; places kind `town`.
- `azt_passage_areas`: AZT Passages Segments (polygons), 138 polygon features; no places kind.
- `azt_land_ownership`: Land Ownership within 10 miles of the Arizona Trail, 32 polygon features; no
  places kind.

ATA's own page /explore/gateway-communities/ lists 20 towns to the layer's 22.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("azt_gateway_communities", "azt_passage_areas", "azt_land_ownership")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
