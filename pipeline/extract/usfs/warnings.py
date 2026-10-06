"""USDA Forest Service: warnings, 3 ArcGIS layers extracted here (decision 53 phase B, 2026-10-03).

- `usfs_r03_fire_restrictions`: USFS Southwestern Region fire restrictions,
  `r03/r03_FireRestriction_01/MapServer/0`.
- `usfs_baer_assessments`: USFS Burned Area Emergency Response assessment boundaries,
  `EDW/EDW_BurnedAreaEmergencyResponse_01/MapServer/0`. Read daily, not on the type's lane: an
  on-prem layer with no maintained date answers its change check UNKNOWN, so each check is a full
  read of 246 burn-scar polygons from the Forest Service's own server. Its row says why phase C
  should hold it back.
- `usfs_r08_prescribed_burns`: USFS Southern Region prescribed burn status,
  `R8_Prescribed_Burn_Status__read_only/FeatureServer/0`. Filtered on the agency's own status field:
  `BURN_STATUS IN ('In Progress', 'Planned for 1-10 days')`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

THE FORESTS' ALERTS PAGES are warnings as much as closures (their levels run from 'critical' to
'information'), and they land once, in usfs/closures.py, as 15 PageNotice tables that the warnings
staging model reads too: a file takes one form, and this one claims the layers above.

NOT WIRED: https://www.wfas.net/, the Wildland Fire Assessment System's front page (no robots.txt,
404; ETag and Last-Modified 2026-09-09, read by decision 53's inventory, batch 4). It is a fire-danger
site of maps and model products, not a notice, and nothing on its front page names a trail
(Reasoned from the inventory's read, which did not parse it). Fire danger reaches warnings through
the state layers already registered (_shared/wa_dnr/, wi_dnr/, njgin/).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/CNF_ClosureAreaPolygons/FeatureServer,
Chugach NF's 22 one-polygon layers of winter motorized closure areas (service Last-Modified
2024-01-11); each is its own layer, so 22 registry rows, deferred: they do not close the footpath;
https://apps.fs.usda.gov/fsgisx02/rest/services/r04/R04_Alerts_And_Closures_01/MapServer/0, a copy
of usfs_r04_forest_orders (the SAME_AS note below).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usfs_r03_fire_restrictions", "usfs_baer_assessments", "usfs_r08_prescribed_burns")
RESOURCES = [
    arcgis_layer("usfs_r03_fire_restrictions"),
    arcgis_layer(
        "usfs_baer_assessments",
        cadence_override="daily",
        cadence_reason="an on-prem layer with no maintained date answers its change check UNKNOWN, so each check is a full read of 246 burn-scar polygons from the Forest Service's own server; assessments arrive days apart (124 since 2025-01-01), so a daily read is enough (@unvalidated: settled by _extract_runs' row counts over a fire season)",
    ),
    arcgis_layer("usfs_r08_prescribed_burns"),
]
