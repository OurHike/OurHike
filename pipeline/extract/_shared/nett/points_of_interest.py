"""NorthEast Texas Trail Coalition: points of interest, held. A candidate steward with no trail_orgs.json row yet, so
it lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every
type, held"). Held until the maintainer approves the coalition's trail_orgs.json row in chat (decision 121); then
this file moves to the club folder of the same name.

- `nett_trail_pois`: `NET_Trail/FeatureServer/0`, 167 trail features typed by a coded domain (2026-10-09): 2 water
  fountains, 7 restrooms and 44 trailheads among them. 8 of the 167 lie outside north-east Texas, which its row
  says must never be drawn on this trail.

Raw only until the steward has a folder of its own. Monthly.
"""

from extract._kinds import arcgis_layer

TYPE = "points_of_interest"
CLAIMS = ("nett_trail_pois",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
