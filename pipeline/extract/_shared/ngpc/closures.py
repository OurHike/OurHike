"""Nebraska Game and Parks Commission: closures, held. A candidate steward with no trail_orgs.json row yet, so it
lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every
type, held"). Every row is held until the maintainer approves the commission's trail_orgs.json row in chat
(decision 121); then these files move to the club folder of the same name.

- `ngpc_cowboy_trail_improvements`: `Cowboy_Trail/FeatureServer/5`, the Cowboy Trail in 29 sections, each with
  a status and a condition (2 closed and impassable on 2026-10-09). One section reads 'Open' and 'Not Passable'
  at once, which its row says no rule may show as open.
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("ngpc_cowboy_trail_improvements",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
