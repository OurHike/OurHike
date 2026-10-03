"""Lewis & Clark Trail Heritage Foundation: trail lines, drawn from nps/'s resources (decision 34),
registered on 2026-10-03.

The water trails are the only "go there and do it" lines, and they are for paddlers

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_lewis_clark_nht` (62 lines), "
        "`nps_lewis_clark_water_trails` (18 lines) registered in sources.json and extracted in "
        "nps/trail_lines.py.",
        "`NPSAGOL/Lewis_and_Clark_National_Historic_Trail_Congressionally_Designated_Route`: 62 lines "
        "(2025-09-30). `LECL_Lewis_and_Clark_NHT_Water_Trails`: 18 lines (2026-09-29; Trail_Name, "
        "Web_URL, Trail_Org). `LECL_…_Auto_Route_Final_Combined`: 3,396. "
        "`Lewis_and_Clark_Trail_Historic_Route`: 57. `nps_trails` LECL: 28 unnamed (LOADED fragment). "
        "Own: none",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://lewisandclark.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/Lewis_and_Clark_National_Historic_Trail_Congressionally_Designated_Route/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/LECL_Lewis_and_Clark_NHT_Water_Trails/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
