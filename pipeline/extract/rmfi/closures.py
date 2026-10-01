"""Rocky Mountain Field Institute: closures, published, and not landed (coverage audit 2026-10-01,
batch p07_persist).

Licence: USFS pages are federal works. The COTREX closures item has an empty licenseInfo, so
none_stated. Folders: `usfs`, `cotrex`, City of Colorado Springs (new).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS: `https://www.fs.usda.gov/r02/psicc/alerts`, HTML, 45 alerts. 8 name the Pikes Peak Ranger "
        'District, among them "Forest Order #02-12-00-24-18 Waldo Canyon Burn Area Closure" (2024-07-19) and '
        '"#02-12-00-23-09 Crags Winter Area Closure" (2023-04-29). COTREX: '
        "`services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/SCs_All_COTREX_Sept2025_Final/FeatureServer/0`"
        ' has 2 seasonal wildlife closures in the envelope: CPW "December 1 - July 15" and USFS "April 1 - July'
        ' 15". Their `Start_Date`/`End_Date` are for the 2024–25 season. City: the web closure page is unread '
        "(robots.txt bars Claude …",
    ),
    where=(
        "https://www.fs.usda.gov/r02/psicc/alerts",
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/SCs_All_COTREX_Sept2025_Final/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
