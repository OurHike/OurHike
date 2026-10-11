"""Illinois Department of Transportation: trail lines, held for scope. IDOT's trail_orgs.json row, `idot` (`load:
hold`), was written on 2026-10-11 because its bicycle inventory carries the Grand Illinois Trail's only published line,
and IL DNR's row points to it (the maintainer's poll, 2026-10-11, review page 02, P10; decision 34: each dataset is
extracted once, in its steward's folder).

- `idot_bike_inventory`: `BFISProductionLayer_prod_view/FeatureServer/0`, IDOT's Bicycle Facility Inventory System,
  12,655 lines statewide (read 2026-10-11): every bike lane, shared-use path, paved shoulder and marked route IDOT
  inventories, 1,088 of them planned and 510 decommissioned. 13 are named for the Grand Illinois Trail, 12 of them
  on-road bike lanes. Keyed on GlobalID, distinct on all 12,655.

Drawn whole, it would show every bike lane in Illinois as trail, so its sources.json row holds it back until a rule
narrows it to the trail's own lines. Monthly, the type's default lane.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("idot_bike_inventory",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
