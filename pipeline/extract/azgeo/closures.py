"""AZGeo Data Hub: closures, drawn from another folder's resource (decision 53 phase B, 2026-10-03).

This club's closures arrive through usfs/ `usfs_r03_forest_orders`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://aztrail.org/wp-json/wp/v2/posts?categories=251&per_page=100&_fields=id,slug,date_gmt,modified_gmt,title,link,categories,tags
(wordpress); https://aztrail.org/category/closures-reroutes/feed/ (rss);
https://aztrail.org/wp-json/wp/v2/categories?slug=closures-reroutes&_fields=id,count,name,slug,link
(wordpress); https://aztrail.org/category/closures-reroutes/ (html_page).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/USFS_Camping_and_Campfire_Restricted_Area/FeatureServer/0,
a 2023 copy of a Coconino NF order (lastEditDate 2023-05-09); the Forest Service's own R3 order
layers in usfs/ are the live channel.

Before decision 53 phase B, 2026-10-03, this note read:

AZGeo Data Hub: closures, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

This goes to `ata/closures.py`. The order belongs to the Forest Service.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_r03_forest_orders` (decision 53 phase B, 2026-10-03): `usfs_r03_forest_orders` reads `r03/r03_ForestOrder_01/MapServer/0`",
        "The ATA closures RSS `https://aztrail.org/category/closures-reroutes/feed/` answered HTTP 200 (12,033 bytes) today; it was listed in org_channels 2026-09-29. `USFS_Camping_and_Campfire_Restricted_Area/0`: 1 Coconino NF order, last edit 2023-05-09 (stale).",
    ),
    where=(
        "https://apps.fs.usda.gov/fsgisx02/rest/services/r03/r03_ForestOrder_01/MapServer/0",
        "https://aztrail.org/category/closures-reroutes/feed/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
