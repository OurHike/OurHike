"""USDA Forest Service: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `usfs_forest_boundaries`: Administrative Forest Boundaries - National Extent, 112 polygon features;
  places kind `park`.
- `usfs_ranger_districts`: Ranger District Boundaries - National Extent, 503 polygon features; no places
  kind.
- `usfs_wilderness_areas`: National Wilderness Areas (USFS), 449 polygon features; places kind `park`.
- `usfs_national_grasslands`: National Grassland Units, 20 polygon features; places kind `park`.
- `usfs_other_designated_areas`: National Forest Lands with Nationally Designated Management or Use
  Limitations, 227 polygon features; places kind `park`.
- `usfs_special_interest_areas`: Special Interest Management Areas, 1,906 polygon features; no places
  kind.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "usfs_forest_boundaries",
    "usfs_ranger_districts",
    "usfs_wilderness_areas",
    "usfs_national_grasslands",
    "usfs_other_designated_areas",
    "usfs_special_interest_areas",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
