"""Idaho Department of Parks and Recreation: closures, held. A candidate steward with no trail_orgs.json row yet, so
it lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every
type, held"). Every row is held until the maintainer approves IDPR's trail_orgs.json row in chat (decision 121);
then these files move to the club folder of the same name. The coverage audit's idpr-coeur-dalenes folds into
this folder (the Trail of the Coeur d'Alenes is IDPR's).

- `idpr_emergency_route_closures`: `Idaho_Recreation_Trails/FeatureServer/127`, the route closures IDPR gathers
  from every Idaho land manager for its Idaho Trails app (51 lines on 2026-10-09).
- `idpr_area_restrictions`: `Idaho_Recreation_Trails/FeatureServer/123`, area closures and restrictions (20
  polygons), its Restricted_Area_Type the category.

Both state their dates as text (DateStart '12/18/2025', DateEnd '12/31/2026 unless rescinded'); the rows' notes
say which seeds/notice_source_fields.csv reads. The Idaho Centennial Trail's maintenance log
(`Idaho_Centennial_Trail_Maintenance_view/FeatureServer/1`, 87 lines) is not here: it records stretches cleared
since 2021, not notices, and waits for the rest of IDPR's layers.
"""

from extract._kinds import arcgis_layer

TYPE = "closures"
CLAIMS = ("idpr_emergency_route_closures", "idpr_area_restrictions")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
