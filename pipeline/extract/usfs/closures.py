"""USDA Forest Service: closures, 10 ArcGIS layers extracted here (decision 53 phase B, 2026-10-03).

- `usfs_rec_opportunities_status`: USFS Recreation Opportunities: sites not open (EDW),
  `EDW/EDW_RecreationOpportunities_01/MapServer/0`. Filtered on the agency's own status field:
  `openstatus NOT IN ('open', 'none')`. Read daily, not on the type's lane: an on-prem layer with no
  maintained date answers its change check UNKNOWN, so every check is a full read of about 3,000
  rows with long descriptions from the Forest Service's own server.
- `usfs_r03_forest_orders`: USFS Southwestern Region forest orders (points),
  `r03/r03_ForestOrder_01/MapServer/0`.
- `usfs_r04_forest_orders`: USFS Intermountain Region forest orders,
  `R04_Forest_Orders_PUBLIC_VIEW/FeatureServer/0`.
- `usfs_r06_fire_closure_points`: USFS Pacific Northwest Region fire closure orders (points),
  `R06_FireClosureOrders_PublicView/FeatureServer/0`. Filtered on the agency's own status field:
  `ClosureStatus = 'Active'`.
- `usfs_r06_fire_closure_lines`: USFS Pacific Northwest Region fire closure orders (lines),
  `R06_FireClosureOrders_PublicView/FeatureServer/1`. Filtered on the agency's own status field:
  `ClosureStatus = 'Active'`.
- `usfs_r06_fire_closure_areas`: USFS Pacific Northwest Region fire closure orders (areas),
  `R06_FireClosureOrders_PublicView/FeatureServer/2`. Filtered on the agency's own status field:
  `ClosureStatus = 'Active'`.
- `usfs_r09_superior_closures`: Superior National Forest closures and alerts,
  `R09_SNF_Public_Info_Closures_and_Alerts/FeatureServer/0`.
- `usfs_r01_bmwc_trail_closures`: Bob Marshall Wilderness Complex current trail closures,
  `R01_BMWC_CurrentTrailClosure_VIEW/FeatureServer/0`.
- `usfs_r01_kootenai_inaccessible`: Kootenai National Forest inaccessible roads and trails,
  `R01_-_KNF_Inaccessible_Roads_and_Trails_View/FeatureServer/2`.
- `usfs_forest_closure_area`: USFS 'Forest Closure Area' (one undated polygon),
  `Forest_Closure_Area/FeatureServer/0`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

SAME_AS below: the on-prem `R04_Alerts_And_Closures_01/MapServer/0` is the same 233 orders as
`usfs_r04_forest_orders`, so it is noted and never extracted.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fs.usda.gov/r08/cherokee/alerts (html_page);
https://www.fs.usda.gov/r08/gwj/alerts (html_page); https://www.wfas.net/ (html_page).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/CNF_ClosureAreaPolygons/FeatureServer,
Chugach NF's 22 one-polygon layers of winter motorized closure areas (service Last-Modified
2024-01-11); each is its own layer, so 22 registry rows, deferred: they do not close the footpath;
https://apps.fs.usda.gov/fsgisx02/rest/services/r04/R04_Alerts_And_Closures_01/MapServer/0, a copy
of usfs_r04_forest_orders (the SAME_AS note below).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

USDA Forest Service: closures, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Format: (a) and (b) are ArcGIS; (c) is a page. The site rejects `?_format=json` with 406 ("Supported
formats: html"); `/jsonapi` and `/alerts/rss.xml` 404; robots.txt has no crawl-delay or alerts rule.
(Skeptic: R02, R08 and R10 do have layers, listed in the evidence. R05 still has none found.) R06 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): No national closure layer in EDW's 145 (Measured). Instead:
(a) regional closure-order layers in AGOL org `gGHDlz6USftL5Pau`, all feature services:
`R06_FireClosureOrders_PublicView` (layer 0 points 2,068, active 174; layer 1 lines 10,509, active
1,536, e.g. Mt. Hood "TANNER BUTTE", order 06-22-01-25-02; layer 2 polygons 547, active 15; edited
2026-09-26); `R04_Forest_Orders_PUBLIC_VIEW/0`, 232 polygons, edited 2026-09-26;
`R09_SNF_Public_Info_Closures_and_Alerts/0` (Superior NF), 210 points, edited 2026-09-30;
`R01_BMWC_CurrentTrailClosure_VIEW/0` (Bob Marshall), 6 trail lines, edited …

Its `where`: https://fs.usda.gov/ https://apps.fs.usda.gov/arcx/rest/services
https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Forest_Closure_Area/FeatureServer/0

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "usfs_rec_opportunities_status",
    "usfs_r03_forest_orders",
    "usfs_r04_forest_orders",
    "usfs_r06_fire_closure_points",
    "usfs_r06_fire_closure_lines",
    "usfs_r06_fire_closure_areas",
    "usfs_r09_superior_closures",
    "usfs_r01_bmwc_trail_closures",
    "usfs_r01_kootenai_inaccessible",
    "usfs_forest_closure_area",
)
RESOURCES = [
    arcgis_layer(
        "usfs_rec_opportunities_status",
        cadence_override="daily",
        cadence_reason="an on-prem layer with no maintained date answers its change check UNKNOWN, so every check is a full read of about 3,000 rows with long descriptions from the Forest Service's own server; read once a day rather than 24 times (@unvalidated: whether a day is short enough, settled by how often openstatus moves in _extract_runs)",
    ),
    arcgis_layer("usfs_r03_forest_orders"),
    arcgis_layer("usfs_r04_forest_orders"),
    arcgis_layer("usfs_r06_fire_closure_points"),
    arcgis_layer("usfs_r06_fire_closure_lines"),
    arcgis_layer("usfs_r06_fire_closure_areas"),
    arcgis_layer("usfs_r09_superior_closures"),
    arcgis_layer("usfs_r01_bmwc_trail_closures"),
    arcgis_layer("usfs_r01_kootenai_inaccessible"),
    arcgis_layer("usfs_forest_closure_area"),
]
SAME_AS = (
    SameAs(
        original="usfs_r04_forest_orders",
        copy=("https://apps.fs.usda.gov/fsgisx02/rest/services/r04/R04_Alerts_And_Closures_01/MapServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "Both layers are named 'ForestOrder' and carry the same 25 attribute fields by name and type (objectid, forestname, ordername, ordernum, ordertype, startdate, enddate, rescinddate, hyperlink, pub_date, crc and the rest), read from each one's ?f=json in the phase A inventory, 2026-10-03.",
            "Both answered returnCountOnly with 233 on 2026-10-03 (inventory batches 1 and 4), and both name the Intermountain Region's Information Management GIS in copyrightText.",
            "Which is the original is Reasoned, not read: the ArcGIS Online view was last edited 2026-10-03 06:21 UTC, the shape of a nightly copy, and it is extracted because its conditional GET answers 304 when nothing moved, where the on-prem layer has no maintained date and would be read whole every hour.",
        ),
    ),
)
