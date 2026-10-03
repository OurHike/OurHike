"""Sierra Buttes Trail Stewardship: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `sbts_trail_town_amenities`: SBTS Amenities (trail-town services), 466 point features; no places kind.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("sbts_trail_town_amenities",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
