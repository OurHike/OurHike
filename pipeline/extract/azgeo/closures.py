"""AZGeo Data Hub: closures, drawn from another folder's resource (decision 53 phase B, 2026-10-03).

This club's closures arrive through usfs/ `usfs_r03_forest_orders`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

The Arizona Trail Association's closures category (https://aztrail.org/category/closures-reroutes/),
which the coverage audit filed here, is ATA's and is read once in ata/closures.py as
`ata_closures_reroutes` (decision 34); its feed and listing page are that category's window and its
human view, and are not read.

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
        "via ata/ `ata_closures_reroutes` (decision 53 phase B, 2026-10-03): WordpressPosts, category 251, X-WP-Total 13",
    ),
    where=(
        "https://apps.fs.usda.gov/fsgisx02/rest/services/r03/r03_ForestOrder_01/MapServer/0",
        "https://aztrail.org/category/closures-reroutes/feed/",
        "https://aztrail.org/category/closures-reroutes/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; and from ata/'s `ata_closures_reroutes`",
)
