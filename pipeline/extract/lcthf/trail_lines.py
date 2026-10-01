"""Lewis & Clark Trail Heritage Foundation: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The water trails are the only "go there and do it" lines, and they are for paddlers

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/Lewis_and_Clark_National_Historic_Trail_Congressionally_Designated_Route`: 62 lines "
        "(2025-09-30). `LECL_Lewis_and_Clark_NHT_Water_Trails`: 18 lines (2026-09-29; Trail_Name, Web_URL, "
        "Trail_Org). `LECL_…_Auto_Route_Final_Combined`: 3,396. `Lewis_and_Clark_Trail_Historic_Route`: 57. "
        "`nps_trails` LECL: 28 unnamed (LOADED fragment). Own: none",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://lewisandclark.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
