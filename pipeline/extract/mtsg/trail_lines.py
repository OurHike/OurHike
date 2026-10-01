"""Mountains to Sound Greenway Trust: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c6_regional_3).

`wa_rco_trails` is in sources.json, but its `reaches_hikers_comment` says "Registered, not shipped".
The Trust's own layers are planning drafts, not something to put in front of a hiker.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "In `WA_RCO_Trails_Database_Public_View/FeatureServer/0`, `UPPER(trail_name) LIKE '%MOUNTAINS TO "
        "SOUND%'` returns 10 segments and `'%MIDDLE FORK SNOQUALMIE%'` returns 5. Own: the `an email address` "
        "ArcGIS account holds 2016–2017 planning layers (`InformalTrails`, `PlannedTrails`, `SnoqValleyTrail` "
        "with 2 polylines). There is also a regional trails PDF, "
        "`/wp-content/uploads/2026/03/2026-RegionalTrails_wText.pdf`. The MTS Greenway Trail page links King "
        'County\'s "Backyard Fun Finder" Experience (`26b4c16e…`, owner `KingCounty`).',
    ),
    where=(
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services/WA_RCO_Trails_Database_Public_View/FeatureServer/0",
        "https://mtsgreenway.org/",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
