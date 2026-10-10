"""Vermont Agency of Transportation (rail trails): closures, held. A candidate steward with no trail_orgs.json row
yet, so it lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll,
2026-10-09: "Every type, held"). Every row is held until the maintainer approves VTrans's trail_orgs.json row in
chat (decision 121); then these files move to the club folder of the same name.

- `vtrans_rail_trail_closures`: `VT_Rail_Trails_Closure_View/FeatureServer/4`, 20 closures on the state's rail
  trails (2026-10-09), 1 of them active by the agency's own isActive flag; the view keeps the ended ones.
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("vtrans_rail_trail_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
