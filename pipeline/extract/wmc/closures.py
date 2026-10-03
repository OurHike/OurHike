"""Wasatch Mountain Club: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through usfs/ `usfs_r04_forest_orders`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fs.usda.gov/r04/uinta-wasatch-cache/alerts
(html_page); https://api.avalanche.org/v2/public/products/map-layer (json_api);
https://wasatchmountainclub.org/announcements (html_page).

Before decision 53 phase B, 2026-10-03, this note read:

Wasatch Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p08_persist).

Licence: USFS is open_licence, federal. Folder: `usfs/closures.py`. The R04 layer serves every R04
club, not just WMC. See Safety finds: the loaded SGID layer still marks the closed Big Cottonwood
trails `EXISTING`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_r04_forest_orders` (decision 53 phase B, 2026-10-03): `usfs_r04_forest_orders` reads `R04_Forest_Orders_PUBLIC_VIEW/FeatureServer/0`",
        "R04 order polygons: `fsgisx02/.../r04/R04_Alerts_And_Closures_01/MapServer/0`, `forestname LIKE 'Uinta%'`: 96 polygons (Safety Closure 52, Closure for Resource Protection 29, Recreation Restriction 9, Motor Vehicle Use Prohibition 4, Firearm Restriction 2). 22 Safety Closures started after 2025-01-01 and end after today. Current ones in WMC's canyons: \"Big Cottonwood Trail Closures\" (04-19-26-744, 2026-08-20 → 2026-11-30): \"Being in or upon the Mineral Fork Trail, Donut Falls Connector Trail, Jordan Pines Connector Trail, Mill D North Fork Trail, and Days Fork Trail. This includes all …",
    ),
    where=(
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/R04_Forest_Orders_PUBLIC_VIEW/FeatureServer/0",
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://wasatchmountainclub.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
