"""Montour Trail Council: points of interest, held. A candidate steward with no trail_orgs.json row yet, so it lives
in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type,
held"). Held until the maintainer approves the council's trail_orgs.json row in chat (decision 121); then this
file moves to the club folder of the same name.

- `montour_trail_access_areas`: `Access_Areas_View/FeatureServer/3`, the trail's 37 access areas with their
  amenities as columns (2026-10-09): a drinking fountain at 9, a shelter at 5.

Its alerts page is closures.py's. Its dated alerts are events in its calendar's JSON, which need a reader nothing has
yet, and wait with its other layers. Raw only until the steward has a folder of its own. Monthly.
"""

from extract._kinds import arcgis_layer

TYPE = "points_of_interest"
CLAIMS = ("montour_trail_access_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
