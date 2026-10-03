"""Bartram Trail Conference: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through usfs/ `usfs_rec_opportunities_status`, each extracted once in
its steward's folder (decision 34). Its portion is assigned in dbt.

The Forest Service's alerts pages for the Chattahoochee-Oconee
(https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts, 30 alerts on 2026-10-03) and the National
Forests in North Carolina (https://www.fs.usda.gov/r08/northcarolina/alerts, 59) are read once, in
usfs/closures.py as `usfs_r08_chattahoochee_oconee_alerts` and `usfs_r08_northcarolina_alerts`
(decision 34), and every club on those forests draws on them. 'Bartram' appears on neither page, so
the club's portion is forest-level until a reviewed term maps an alert.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services/gamelands_general/FeatureServer/21,
NCWRC's 95 game-land boundaries with no season dates: a places geography, not a notice;
https://services6.arcgis.com/9QlSLDqa0P1cHLhu/arcgis/rest/services/WRD_WMA_Public/FeatureServer/14,
Georgia WRD's 222 WMA boundaries with no dates: a places geography, not a notice.

Before decision 53 phase B, 2026-10-03, this note read:

Bartram Trail Conference: closures, published, and not landed (coverage audit 2026-10-01, batch
q01_persist).

`openstatus` is a facility status, not a trail closure; nothing in EDW marks a closed trail segment.
Licence: USFS, public domain (17 U.S.C. 105, `usfs_licence`), a federal work → open_licence (public
domain, federal). Folder: `usfs/` (EDW layer and per-forest alerts pages, as b6 lists them).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_rec_opportunities_status` (decision 53 phase B, 2026-10-03): `usfs_rec_opportunities_status` reads `EDW/EDW_RecreationOpportunities_01/MapServer/0`",
        'GIS: `https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0` `openstatus`, within 1 km of the 126.42-mi `usfs_trails` Bartram line (7 features): 8 rec sites, open 4, temporarily closed 3 ("Russell Farmstead", "Appletree Group Campground", "Wine Spring Horse Camp"), none 1. Forest-wide: Chattahoochee-Oconee temporarily closed 9 / closed 2 / open 63; NFs in North Carolina temporarily closed 12 / closed 16 / none 17 / open 112. Pages: `https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts`, 30 alert links (e.g. …',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0",
        "https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts",
        "https://www.fs.usda.gov/r08/northcarolina/alerts",
        "https://bartramtrail.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; and from its alerts pages, `usfs_r08_chattahoochee_oconee_alerts` and `usfs_r08_northcarolina_alerts`",
)
