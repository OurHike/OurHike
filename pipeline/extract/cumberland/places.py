"""Cumberland Trail / Tennessee State Parks: places, extracted (decision 54, wave 1; live read 2026-10-03
under lib/user_agent.py's USER_AGENT).

- `tn_state_park_boundaries`: Tennessee State Park Boundaries (Public View), 68 polygon features; places
  kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("tn_state_park_boundaries",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
