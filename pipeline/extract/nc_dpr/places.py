"""NC Division of Parks & Recreation — NC Trails: places, extracted (decision 54, wave 1; live read
2026-10-03 under lib/user_agent.py's USER_AGENT).

- `nc_state_park_boundaries`: NC State Parks Boundaries, 346 polygon features; places kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nc_state_park_boundaries",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
