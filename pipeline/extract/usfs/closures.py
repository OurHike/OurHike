"""USDA Forest Service: closures, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Format: (a) and (b) are ArcGIS; (c) is a page. The site rejects `?_format=json` with 406 ("Supported
formats: html"); `/jsonapi` and `/alerts/rss.xml` 404; robots.txt has no crawl-delay or alerts rule.
(Skeptic: R02, R08 and R10 do have layers, listed in the evidence. R05 still has none found.) R06 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No national closure layer in EDW's 145 (Measured). Instead: (a) regional closure-order layers in AGOL "
        "org `gGHDlz6USftL5Pau`, all feature services: `R06_FireClosureOrders_PublicView` (layer 0 points "
        '2,068, active 174; layer 1 lines 10,509, active 1,536, e.g. Mt. Hood "TANNER BUTTE", order '
        "06-22-01-25-02; layer 2 polygons 547, active 15; edited 2026-09-26); "
        "`R04_Forest_Orders_PUBLIC_VIEW/0`, 232 polygons, edited 2026-09-26; "
        "`R09_SNF_Public_Info_Closures_and_Alerts/0` (Superior NF), 210 points, edited 2026-09-30; "
        "`R01_BMWC_CurrentTrailClosure_VIEW/0` (Bob Marshall), 6 trail lines, edited …",
    ),
    where=(
        "https://fs.usda.gov/",
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Forest_Closure_Area/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
