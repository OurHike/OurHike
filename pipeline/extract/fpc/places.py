"""Forest Park Conservancy: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `fpc_ancient_forest_preserve`: Ancient Forest Preserve boundary (Forest Park Conservancy), 1 polygon
  feature; places kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fpc_ancient_forest_preserve",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
