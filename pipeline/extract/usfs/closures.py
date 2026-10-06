"""USDA Forest Service: closures, 10 ArcGIS layers and 15 forests' alerts pages extracted here (decision 53 phase B,
2026-10-03).

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

THE FORESTS' ALERTS PAGES, one PageNotice each (extract/_notices.py), every one read live under our
agent on 2026-10-03 after www.fs.usda.gov's robots.txt (a `User-agent: *` group of Drupal internals,
no Crawl-delay, nothing matching `/<region>/<forest>/alerts`). They are the Forest Service's, so they
land here once (decision 34) and the clubs that draw on them carry `via` notes naming this file:
alaska_trails and iditarod (r10/chugach), black_hills (r02/blackhills), bartram, cmc, nc_high_peaks
and nc_mst (r08/northcarolina), bartram and pinhoti (r08/chattahoochee-oconee), catamount (r09/gmfl),
condor (r05/lospadres), mdhta (r01/dpg), nez_perce (trails/nez-perce-nht), ouachita (r08/ouachita),
path (r08/gwj), pinhoti (r08/alabama), rmc (r09/whitemountain), rmfi (r02/psicc), wmc
(r04/uinta-wasatch-cache), and tehcc (r08/cherokee).

Each page is the one template every forest shares: a <main> whose <h1> is 'Alerts', alert cards
by level (critical, fire-restriction, caution, information) after a four-card legend, each card a
stable `/alerts/<slug>` link with its own 'Alert Start Date', and no pager or feed. 0 to 90 cards a
page on 2026-10-03 (each row's notes count them). The reader lands the page's title, a hash of
<main>'s text and the link, so `expect_title='Alerts'` refuses a page that turned into something
else, and `date_pattern=None` because the page states no date of its own: a card's start date is
the card's. Two reads about ten minutes apart hashed the same on all 15 (Measured), so the hourly
read does not move every hour. The listing names no person; the detail pages do (GWJ's name staff
with e-mail addresses, the coverage audit), and they are not read. A per-alert reader keyed on the
slug is what phase A's evidence supports next. The alerts are closures and warnings both, and the
warnings staging model reads these tables too, since a file takes one form.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/CNF_ClosureAreaPolygons/FeatureServer,
Chugach NF's 22 one-polygon layers of winter motorized closure areas (service Last-Modified
2024-01-11); each is its own layer, so 22 registry rows, deferred: they do not close the footpath;
https://apps.fs.usda.gov/fsgisx02/rest/services/r04/R04_Alerts_And_Closures_01/MapServer/0, a copy
of usfs_r04_forest_orders (the SAME_AS note below).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer, page_notice

# The forests' alerts pages, one registry row each (sources.json, provider USFS).
ALERTS_PAGES = (
    "usfs_r08_cherokee_alerts",
    "usfs_r08_gwj_alerts",
    "usfs_r08_northcarolina_alerts",
    "usfs_r08_alabama_alerts",
    "usfs_r08_chattahoochee_oconee_alerts",
    "usfs_r08_ouachita_alerts",
    "usfs_r09_whitemountain_alerts",
    "usfs_r09_gmfl_alerts",
    "usfs_r02_psicc_alerts",
    "usfs_r02_blackhills_alerts",
    "usfs_r04_uinta_wasatch_cache_alerts",
    "usfs_r10_chugach_alerts",
    "usfs_r01_dpg_alerts",
    "usfs_r05_lospadres_alerts",
    "usfs_nez_perce_nht_alerts",
)

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
    *ALERTS_PAGES,
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
    *(page_notice(key, expect_title="Alerts", date_pattern=None) for key in ALERTS_PAGES),
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
