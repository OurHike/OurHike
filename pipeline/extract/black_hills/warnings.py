"""Black Hills Trails: warnings, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's warnings arrive through _shared/nifc/ `nifc_wfigs_current_perimeters`, each extracted
once in its steward's folder (decision 34). Its portion is assigned in dbt.

BLM's Montana-Dakotas press releases (https://www.blm.gov/press-release/montana-dakotas/rss) are
read once, in blm/warnings.py as `blm_press_montana_dakotas` (decision 34). The Black Hills NF's
alerts page (https://www.fs.usda.gov/r02/blackhills/alerts, 27 alerts on 2026-10-03, among them
'Pactola North Boat Ramp Closure' from October 5) is the Forest Service's, read once in
usfs/closures.py as `usfs_r02_blackhills_alerts`.

Before decision 53 phase B, 2026-10-03, this note read:

Black Hills Trails: warnings, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

WFIGS licenseInfo: "The National Interagency Fire Center shall not be held liable for improper or
incorrect use of the data described and/or contained herein…". That is none_stated (a disclaimer) on
an interagency federal product. Folders: `usfs/`, `blm/`, `_shared/` NIFC (name Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/nifc/ `nifc_wfigs_current_perimeters` (decision 53 phase B, 2026-10-03): `nifc_wfigs_current_perimeters` reads `WFIGS_Interagency_Perimeters_Current/FeatureServer/0`",
        'Same BH NF alerts page: "Open Fire Restriction - Black Hills NF in South Dakota" (fire-restriction, 2024-11-16); "Stage 2 Fire Restrictions in Black Hills NF in Wyoming" (2026-09-24); "Topaz timber sale near Sturgis, SD Continues Operations" (caution: "Tethered logging with chipping/mastication may cause flying debris near trails"); "Please Use Caution When Entering the Black Elk Wilderness" (falling trees; the Centennial Trail crosses that wilderness). BLM RSS: "BLM South Dakota Enters Stage 2 Fire Restrictions" (2026-07-15). NIFC …',
        "via blm/ `blm_press_montana_dakotas` (decision 53 phase B, 2026-10-03): FeedNotices, 50 items read live, a window",
    ),
    where=(
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0",
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services3.arcgis.com/NbEEwwcVRO4AIaWE/arcgis/rest/services",
        "https://blackhillstrails.org/",
        "https://www.blm.gov/press-release/montana-dakotas/rss",
    ),
    reason="drawn from _shared/nifc/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; and from blm/'s `blm_press_montana_dakotas` and usfs/'s `usfs_r02_blackhills_alerts`",
)
