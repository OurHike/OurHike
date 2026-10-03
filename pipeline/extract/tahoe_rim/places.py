"""Tahoe Rim Trail Association: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `trta_special_management_areas`: Tahoe Rim Trail special management areas, 7 polygon features; places
  kind `park`.
- `trta_desolation_wilderness_zones`: Desolation Wilderness zones, 49 polygon features; no places kind.
- `trta_trail_sections`: Tahoe Rim Trail sections, 85 polyline features; no places kind.

Camping_Permitted, Camping_Prohibited, Use_Restrictions and EldoradoNationalForestBoundary in the same
organization were not read.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("trta_special_management_areas", "trta_desolation_wilderness_zones", "trta_trail_sections")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
