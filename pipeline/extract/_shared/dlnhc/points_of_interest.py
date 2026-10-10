"""Delaware & Lehigh National Heritage Corridor: points of interest, held. A candidate steward with no
trail_orgs.json row yet, so it lives in _shared/ under the folder its row would name (decision 122, the
maintainer's poll, 2026-10-09: "Every type, held"). Held until the maintainer approves the corridor's
trail_orgs.json row in chat (decision 121); then this file moves to the club folder of the same name.

- `dlnhc_trailheads`: `DL_Trailheads_V2/FeatureServer/0`, the D&L Trail's 64 trailheads with their amenities
  (2026-10-09): potable water at 5, and 11 trailheads still to be built. Its `updatedBy` names the people who
  inspected each one, and is left out by the row's person_fields.

The trail map's section status (mapdata.json) needs a reader nothing has yet, and waits with the corridor's other
layers. Raw only until the steward has a folder of its own. Monthly.
"""

from extract._kinds import arcgis_layer

TYPE = "points_of_interest"
CLAIMS = ("dlnhc_trailheads",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
