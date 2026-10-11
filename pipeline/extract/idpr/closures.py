"""Idaho Department of Parks and Recreation: closures. IDPR's trail_orgs.json row, `idpr` (`load: ship`), was approved
on 2026-10-11 (decision 121, review page 01), so this file moved here from _shared/idpr/, where decision 122 had loaded
it held, and every raw table kept its name. The coverage audit's idpr-coeur-dalenes folds into this folder (the Trail
of the Coeur d'Alenes is IDPR's).

- `idpr_emergency_route_closures`: `Idaho_Recreation_Trails/FeatureServer/127`, the route closures IDPR gathers
  from every Idaho land manager for its Idaho Trails app (51 lines on 2026-10-09).
- `idpr_area_restrictions`: `Idaho_Recreation_Trails/FeatureServer/123`, area closures and restrictions (20
  polygons), its Restricted_Area_Type the category.

Both state their dates as text (DateStart '12/18/2025', DateEnd '12/31/2026 unless rescinded'); the rows' notes
say which seeds/notice_source_fields.csv reads. Their item's terms ask for source attribution in a third-party app,
which rule 5 reads as a credit condition the rows' attribution meets (the maintainer's poll, 2026-10-11, P2). The
Idaho Centennial Trail's maintenance log (`Idaho_Centennial_Trail_Maintenance_view/FeatureServer/1`, 87 lines) is
not here: it records stretches cleared since 2021, not notices, and waits for the rest of IDPR's layers.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("idpr_emergency_route_closures", "idpr_area_restrictions")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
