"""Utah UGRC — SGID Trails and Pathways: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `ugrc_municipal_boundaries`: Utah Municipal Boundaries, 261 polygon features; places kind `town`.
- `ugrc_state_park_boundaries`: Utah state park boundaries (dissolved), 47 polygon features; places kind
  `park`.
- `ugrc_state_park_points`: Utah state park points (for website), 54 point features; no places kind.
- `ugrc_cities_towns`: Utah City and Town Locations, 462 point features; places kind `town`.
- `ugrc_local_parks`: Utah Parks Local, 2,104 polygon features; places kind `park`.

UtahGNISPlaceNames (32,577 points) is USGS's GNIS republished for Utah, and UtahWildernessAreas (67)
compiles the USFS and BLM wildernesses usfs/ and blm/ register (the coverage audit's wmc row:
'EDW_Wilderness_02 has the same three wildernesses'), so neither is registered.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "ugrc_municipal_boundaries",
    "ugrc_state_park_boundaries",
    "ugrc_state_park_points",
    "ugrc_cities_towns",
    "ugrc_local_parks",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
