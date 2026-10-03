"""Tennessee Trails Association: trail lines, nothing published (coverage audit 2026-10-01, batch
p09_persist).

Licence on the statewide layer: "The State of Tennessee makes no representation or warranty as to
the accuracy of this data … The user accepts this data on an 'AS IS' basis". That is none_stated (a
disclaimer, not a restriction), so it is presumed reusable under 21(a). The data belongs to the land
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "TTA owns no geometry anywhere this pass looked. Tennessee's statewide aggregate is "
        "`https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services/Tennessee_Statewide_Trails_Lines_Public/FeatureServer/0`"
        ' (ArcGIS, owner a personal ArcGIS account, org "State of Tennessee STS GIS", urlKey `tnmap`). It holds'
        " 4,199 lines, `dataLastEditDate` 2026-09-30. Its `Managing_Entity_Name` field names 17 NGO managers on"
        " 190 rows (Rivers Management Society 108, Appalachian Trail Conservancy 48, Audubon Acres 10 …). 0 "
        "rows have a manager, `Trail_Name` or `Website` matching TTA. Tried: (1) TTA runs no …",
    ),
    where=(
        "https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services/Tennessee_Statewide_Trails_Lines_Public/FeatureServer/0",
        "https://tennesseetrails.org/",
    ),
)
