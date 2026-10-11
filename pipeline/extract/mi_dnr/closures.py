"""Michigan Department of Natural Resources: closures. The DNR's trail_orgs.json row, `mi-dnr` (`load: ship`), was
approved on 2026-10-11 (decision 121, review page 01), so these files moved here from _shared/mi_dnr/, where decision
122 had loaded them held, and every raw table kept its name. The coverage audit's mi-dnr-high-country folds into this
folder (the High Country Pathway is the DNR's).

- `mi_dnr_trail_temporary_closures`: `DNRTrailsOPENDATA/FeatureServer/0`, 207 lines on 2026-10-09, one
  Open/Closed status per use; 82 carry a 'Temporarily Closed' status for foot travel.

On the DNR's own ArcGIS Server: the change check is the statistics fingerprint on last_edited_date and the
summed length (the row's `freshness`).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("mi_dnr_trail_temporary_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
