"""US Fish & Wildlife Service: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `usfws_refuge_boundaries`: FWS National Realty Boundaries (National Wildlife Refuge System), 1,085
  polygon features; places kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usfws_refuge_boundaries",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
