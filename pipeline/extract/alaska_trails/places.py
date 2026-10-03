"""Alaska Trails: places, extracted (decision 54, wave 1; live read 2026-10-03 under lib/user_agent.py's
USER_AGENT).

- `aklt_communities`: Alaska Long Trail communities and places (AKLT_POI), 42 point features; places
  kind `town`.
- `aklt_story_map_pins`: Alaska Long Trail story map pins, 36 point features; places kind `town`.

ALT_Recreation_LandOwnership_and_Boundaries (4,476 polygons) is a copy of BLM's land data (coverage
audit) and is not registered; the five regional Story_Map_Pins services are not read.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("aklt_communities", "aklt_story_map_pins")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
