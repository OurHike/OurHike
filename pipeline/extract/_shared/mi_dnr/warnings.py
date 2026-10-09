"""Michigan Department of Natural Resources: warnings, held (decision 122; see closures.py beside this file).

- `mi_dnr_trail_temporary_reroutes`: `DNRTrailsOPENDATA/FeatureServer/1`, the lines 11 reroutes follow while a
  closure stands (2026-10-09): a detour to take, never a closure.
- `mi_dnr_burn_permits`: `DNR/Burn_Permits/MapServer/0` on the State's own server, 83 county polygons behind
  "Can I burn today?". A burn permit is about debris burning, a fire-danger proxy and never a rating, and the
  layer publishes no legend for its STATUS codes 0 to 3, so nothing words it for a hiker until the DNR's own page
  says what each means. About 9.4 MB at full resolution, read again only when its PullStamp moves.
"""

from extract._kinds import arcgis_layer

TYPE = "warnings"
CLAIMS = ("mi_dnr_trail_temporary_reroutes", "mi_dnr_burn_permits")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
