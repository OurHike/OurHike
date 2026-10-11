"""Oregon Parks and Recreation Department: points of interest. OPRD's trail_orgs.json row, `oprd` (`load: ship`), was
approved on 2026-10-11 (decision 121, review page 01), so these files moved here from _shared/oprd/, where decision
122 had loaded them held, and every raw table kept its name. The coverage audit's odot folds into this folder.

- `oprd_rec_facilities`: `OPRD_Rec_Features_View_Hosted_view/FeatureServer/3`, 826 facilities at Oregon's state
  parks (2026-10-09), 28 of them 'Drinking Water'.

OPRD's park notices (the park pages' notices JSON) need a reader nothing has yet, and wait with its other layers.
make_dbt_staging.py stages these points now that the steward has a folder of its own; no seeds/club_poi_types.csv row
types FACILITY_TYPE yet, so none of them publishes until one does. Monthly.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprd_rec_facilities",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
