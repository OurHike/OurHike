"""Michigan Department of Natural Resources: closures, held. A candidate steward with no trail_orgs.json row yet,
so it lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09:
"Every type, held"). Every row is held until the maintainer approves the DNR's trail_orgs.json row in chat
(decision 121); then these files move to the club folder of the same name. The coverage audit's
mi-dnr-high-country folds into this folder (the High Country Pathway is the DNR's).

- `mi_dnr_trail_temporary_closures`: `DNRTrailsOPENDATA/FeatureServer/0`, 207 lines on 2026-10-09, one
  Open/Closed status per use; 82 carry a 'Temporarily Closed' status for foot travel.

On the DNR's own ArcGIS Server: the change check is the statistics fingerprint on last_edited_date and the
summed length (the row's `freshness`).
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("mi_dnr_trail_temporary_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
