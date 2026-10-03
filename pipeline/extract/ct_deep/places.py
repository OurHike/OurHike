"""Connecticut DEEP: places, extracted (decision 54, wave 1; live read 2026-10-03 under lib/user_agent.py's
USER_AGENT).

- `ct_deep_property`: DEEP Property (state parks, forests and wildlife areas), 491 polygon features;
  places kind `park`.
- `ct_deep_greenways`: Official Designated Connecticut Greenways, 120 polyline features; no places kind.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ct_deep_property", "ct_deep_greenways")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
