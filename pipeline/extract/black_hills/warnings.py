"""Black Hills Trails: warnings, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

WFIGS licenseInfo: "The National Interagency Fire Center shall not be held liable for improper or
incorrect use of the data described and/or contained herein…". That is none_stated (a disclaimer) on
an interagency federal product. Folders: `usfs/`, `blm/`, `_shared/` NIFC (name Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same BH NF alerts page: "Open Fire Restriction - Black Hills NF in South Dakota" (fire-restriction, '
        '2024-11-16); "Stage 2 Fire Restrictions in Black Hills NF in Wyoming" (2026-09-24); "Topaz timber sale'
        ' near Sturgis, SD Continues Operations" (caution: "Tethered logging with chipping/mastication may '
        'cause flying debris near trails"); "Please Use Caution When Entering the Black Elk Wilderness" '
        '(falling trees; the Centennial Trail crosses that wilderness). BLM RSS: "BLM South Dakota Enters Stage'
        ' 2 Fire Restrictions" (2026-07-15). NIFC …',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services3.arcgis.com/NbEEwwcVRO4AIaWE/arcgis/rest/services",
        "https://blackhillstrails.org/",
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
