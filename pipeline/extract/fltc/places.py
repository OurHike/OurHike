"""Finger Lakes Trail Conference: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `fltc_map_sheet_index`: FLT Index Rectangles (map-sheet areas), 54 polygon features; no places kind.

PostOffices, the 27 resupply towns, is a Category of Waypoints/FeatureServer/8, the points_of_interest
file's upstream: one upstream, so no second resource here.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fltc_map_sheet_index",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
