"""Florida State Parks (Florida DEP's Division of Recreation and Parks): closures. Its trail_orgs.json row,
`fl-state-parks` (`load: ship`), was approved on 2026-10-11 (decision 121, review page 01), so this file moved here from
_shared/fl_state_parks/, where decision 122 had loaded it held, and every raw table kept its name. The coverage audit's
fl-state-parks-fkoht folds into this folder (the Florida Keys Overseas Heritage Trail is a state park).

- `fl_state_parks_day_use_status`: `Florida_State_Parks_Operational_Status/FeatureServer/6`, each park's status
  (176; 35 closed for a hurricane or tropical storm on 2026-10-09).
- `fl_state_parks_campground_status`: `.../FeatureServer/5`, each campground's status (184 rows, 120 of them
  parks with no campground).

A closed park or campground is not by itself a closed trail. The maintainer chose what a park closed for a storm does
(the poll of 2026-10-11, review page 01, P5): it closes the trails inside it until the park's own status reopens it.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fl_state_parks_day_use_status", "fl_state_parks_campground_status")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
