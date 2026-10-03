"""Mountains to Sound Greenway Trust: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `mtsg_heritage_area_boundary`: Mountains to Sound Greenway National Heritage Area boundary, 1 polygon
  feature; places kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("mtsg_heritage_area_boundary",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
