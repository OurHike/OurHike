"""Pacific Crest Trail Association: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `pcta_trail_towns`: PCT Trail Town Resupply points, 106 point features; places kind `town`.
- `pcta_letter_sections`: PCT Letter Sections, 29 polyline features; no places kind.
- `pcta_centerline_regions`: PCT Centerline Regions, 6 polyline features; no places kind.
- `pcta_permit_areas`: PCT Permit Areas, 32 polygon features; no places kind.
- `pcta_wilderness_areas`: Wilderness Areas along the PCT (CA, OR, WA), 253 polygon features; places
  kind `park`.
- `pcta_sheriffs_offices`: PCT county sheriff's offices, 45 polygon features; no places kind.

Trail_Town_Resupply_Walkable_Transit_Accessible_Public, USFS_Forest_Admin_Boundaries,
USFS_Ranger_Districts and the rest of PCTA's 100-odd services were not read; the forest and district
ones copy USFS's.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "pcta_trail_towns",
    "pcta_letter_sections",
    "pcta_centerline_regions",
    "pcta_permit_areas",
    "pcta_wilderness_areas",
    "pcta_sheriffs_offices",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
