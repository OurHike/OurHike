"""Florida Trail Association: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c10_nst_rest).

About 88% of the trail reaches no hiker today. The service name contains a space, which must be
encoded as `%20`. `Trail_Stat` separates footpath from road-walk gaps, which a hiker needs. "LOADED"
is literally true and badly understates the gap.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Arrives via `usfs` as `usfs_trails`, but only 183.6 mi: 26 EDW segments named `FNST - …` across "
        "admin_org 080501–080506. FTA's own: "
        "`https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/FNST%20Master/FeatureServer/0` "
        "(item `2c24002d6c204f1b859b8ab51259ec0d`): 745 segments, 1,568.8 mi. `Open_Statu`: Open 742 (1,567.5 "
        "mi), Closed 3 (1.3 mi). `Trail_Stat`: EXISTING 578 (1,142.7 mi), GAP REQUIRES ACQUISITION 115 (295.1 "
        "mi), GAP NO ACQUISITION 37 (88.9 mi). `Blaze`: Orange 639, Blue 98, White 8. Last edit 2026-07-31. "
        "Also `Florida_National_Scenic_Trail_WFL1/0` (745, last edit …",
    ),
    where=("https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/FNST%20Master/FeatureServer/0",),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
