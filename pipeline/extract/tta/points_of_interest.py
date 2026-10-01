"""Tennessee Trails Association: points of interest, nothing published (coverage audit 2026-10-01,
batch p09_persist).

TNMap points licence: the same AS-IS disclaimer, none_stated. Folders: `tn-state-parks/`, `usfs/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "TTA itself publishes none. Its event-venue REST (153 venues) is a places row and is terms-blocked "
        "(audit). Land-manager POIs found: TDEC `TN_State_Parks_Recreation_Assets_(Public_View)` (item "
        "`18cf8d2d4b4143acb61135a2f82d7681`) and `Public_Hiking_Assets_TN_State_Parks` (1,369 points, c9); "
        "TNMap `Tennessee_Statewide_Trails_Points_Public` (item `87d9ef12e5344055874217c73dec1aa1`, trailhead "
        'points "where the state does not have linear data"); Cherokee NF through `usfs_rec_sites` (LOADED). '
        "Tried: items 1 to 6 as for trail_lines.",
    ),
    where=(
        "https://services.arcgis.com/lvPBAGXeSupVUvx2/arcgis/rest/services",
        "https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services",
        "https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services",
        "https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services",
        "https://tennesseetrails.org/",
    ),
)
