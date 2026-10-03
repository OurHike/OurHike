"""Rocky Mountain Field Institute: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through cotrex/ `cotrex_seasonal_closures`, each extracted once in its
steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fs.usda.gov/r02/psicc/alerts (html_page);
https://coloradosprings.gov/ (City trail-closure page; no URL recorded by the audit) (html_page).

Before decision 53 phase B, 2026-10-03, this note read:

Rocky Mountain Field Institute: closures, published, and not landed (coverage audit 2026-10-01,
batch p07_persist).

Licence: USFS pages are federal works. The COTREX closures item has an empty licenseInfo, so
none_stated. Folders: `usfs`, `cotrex`, City of Colorado Springs (new).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via cotrex/ `cotrex_seasonal_closures` (decision 53 phase B, 2026-10-03): `cotrex_seasonal_closures` reads `SCs_All_COTREX_Sept2025_Final/FeatureServer/0`",
        'USFS: `https://www.fs.usda.gov/r02/psicc/alerts`, HTML, 45 alerts. 8 name the Pikes Peak Ranger District, among them "Forest Order #02-12-00-24-18 Waldo Canyon Burn Area Closure" (2024-07-19) and "#02-12-00-23-09 Crags Winter Area Closure" (2023-04-29). COTREX: `services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/SCs_All_COTREX_Sept2025_Final/FeatureServer/0` has 2 seasonal wildlife closures in the envelope: CPW "December 1 - July 15" and USFS "April 1 - July 15". Their `Start_Date`/`End_Date` are for the 2024–25 season. City: the web closure page is unread (robots.txt bars Claude …',
    ),
    where=(
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/SCs_All_COTREX_Sept2025_Final/FeatureServer/0",
        "https://www.fs.usda.gov/r02/psicc/alerts",
    ),
    reason="drawn from cotrex/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
