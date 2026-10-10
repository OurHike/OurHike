"""The Trail Foundation (Austin): places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `ttc_management_areas`: TTC Management Areas (Lady Bird Lake), 269 polygon features; places kind
  `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ttc_management_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
