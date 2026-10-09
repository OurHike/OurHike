"""Florida State Parks (Florida DEP's Division of Recreation and Parks): closures, held. A candidate steward with no
trail_orgs.json row yet, so it lives in _shared/ under the folder its row would name (decision 122, the
maintainer's poll, 2026-10-09: "Every type, held"). Every row is held until the maintainer approves its
trail_orgs.json row in chat (decision 121); then these files move to the club folder of the same name. The
coverage audit's fl-state-parks-fkoht folds into this folder (the Florida Keys Overseas Heritage Trail is a state
park).

- `fl_state_parks_day_use_status`: `Florida_State_Parks_Operational_Status/FeatureServer/6`, each park's status
  (176; 35 closed for a hurricane or tropical storm on 2026-10-09).
- `fl_state_parks_campground_status`: `.../FeatureServer/5`, each campground's status (184 rows, 120 of them
  parks with no campground).

A closed park or campground is not a closed trail, so neither would ever close one.
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("fl_state_parks_day_use_status", "fl_state_parks_campground_status")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
