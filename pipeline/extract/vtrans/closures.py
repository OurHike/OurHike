"""Vermont Agency of Transportation (rail trails): closures. VTrans's trail_orgs.json row, `vtrans` (`load: ship`), was
approved on 2026-10-11 (decision 121, review page 01), so these files moved here from _shared/vtrans/, where decision
122 had loaded them held, and every raw table kept its name.

- `vtrans_rail_trail_closures`: `VT_Rail_Trails_Closure_View/FeatureServer/4`, 20 closures on the state's rail
  trails (2026-10-09), 1 of them active by the agency's own isActive flag; the view keeps the ended ones.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("vtrans_rail_trail_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
