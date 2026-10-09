"""Oregon Parks and Recreation Department: points of interest, held. A candidate steward with no trail_orgs.json
row yet, so it lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll,
2026-10-09: "Every type, held"). Held until the maintainer approves OPRD's trail_orgs.json row in chat (decision
121); then this file moves to the club folder of the same name. The coverage audit's odot folds into this folder.

- `oprd_rec_facilities`: `OPRD_Rec_Features_View_Hosted_view/FeatureServer/3`, 826 facilities at Oregon's state
  parks (2026-10-09), 28 of them 'Drinking Water'.

OPRD's park notices (the park pages' notices JSON) need a reader nothing has yet, and wait with its other layers.
Raw only until the steward has a folder of its own. Monthly.
"""

from extract._kinds import arcgis_layer

TYPE = "points_of_interest"
CLAIMS = ("oprd_rec_facilities",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
