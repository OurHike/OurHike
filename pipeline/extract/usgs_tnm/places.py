"""USGS — The National Map: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `usgs_gnis_populated_places`: GNIS Populated Places (The National Map), 176,566 multipoint features;
  places kind `town`.

govunits/MapServer/24, Incorporated Place (19,725 polygons, GLOBALID unique), republishes the Census's
place boundaries and is not registered; geonames' other layers (landforms, streams) are not places.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usgs_gnis_populated_places",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
