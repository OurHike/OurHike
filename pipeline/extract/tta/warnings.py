"""Tennessee Trails Association: warnings, nothing published (coverage audit 2026-10-01, batch
p09_persist).

Burn ban licenseInfo: "Tennessee Department of Agriculture, Division of Forestry has attempted to
ensure the accuracy … provided 'as is' without …". TWRA licenseInfo is empty. Both are none_stated.
Folders: a `_shared/` TN forestry folder and a `twra` folder (names Reasoned), plus
`tn-state-parks/` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Land-agency layers for TN hazards: TN Division of Forestry "
        "`https://services.arcgis.com/lvPBAGXeSupVUvx2/arcgis/rest/services/Burn_Ban_WFL1/FeatureServer/0` "
        "\"Burn Ban County Status\": 95 counties, `Ban_Status` = 'None' on all 95, last edit 2026-04-17. TWRA "
        "`https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services/Hunting_Allowed/FeatureServer/0`: "
        "226 polygons (where hunting is allowed, not when), last edit 2026-06-05. Cherokee NF "
        "`roan-mountain-fire-restrictions` alert. tnstateparks.com `/api/alerts` (c9; behind a user-agent "
        "filter). Tried: items 2 to 5 and 7, as above.",
    ),
    where=(
        "https://services.arcgis.com/lvPBAGXeSupVUvx2/arcgis/rest/services/Burn_Ban_WFL1/FeatureServer/0",
        "https://services3.arcgis.com/PWXNAH2YKmZY7lBq/arcgis/rest/services/Hunting_Allowed/FeatureServer/0",
        "https://tnstateparks.com",
        "https://tennesseetrails.org/",
    ),
)
