"""NorthEast Texas Trail Coalition: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in
_shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held").
Held until the maintainer approves the coalition's trail_orgs.json row in chat (decision 121); then this file moves
to the club folder of the same name.

- `nett_damaged_bridges`: `NET_KML_Damaged_Bridges/FeatureServer/0`, 3 bridges collapsed or burned (2026-10-09),
  each dated only in its popup's prose (2014 to 2017), and last edited 2018. Nothing on the layer says any of the
  three is current, so its row says a hiker sees one only with its date.
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("nett_damaged_bridges",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
