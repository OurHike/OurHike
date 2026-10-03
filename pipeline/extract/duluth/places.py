"""City of Duluth Open Data: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `duluth_park_boundaries`: City of Duluth parks, 165 polygon features; places kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("duluth_park_boundaries",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
