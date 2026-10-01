"""AMC Berkshire Chapter: warnings, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

DCR layer: licenseInfo, accessInformation and copyrightText are all empty, so none_stated, presumed
reusable under 21(a). DCR is the land manager at Mount Greylock and the state forests the A.T.
crosses in MA; which of those parks are DCR's was not checked against the layer's `PARK_SITE`
vocabulary …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/FACILITYCLOSURE_APPDATA/FeatureServer/0`"
        ' (item `08be39f7ede549a089385fa07d169fa3`, org "MA Executive Office of Energy and Environmental '
        'Affairs"). It is the layer behind the dashboards "DCR Park Alerts and Advisories" '
        '(`2a639065568e4360b473c76ace4c3442`) and "…_IndividualPages" (`1daa368f04c645a18cb53ba92ebfce4f`). It '
        "holds 2 points today, last edit 2026-10-01 08:25 UTC. Fields include `PARK_SITE`, `ParkAlertType`, "
        "`PAdv_Type`, `PAdv_TypeCategory`, `PAdv_HeaderText`, `PAdv_AlertText`, `PAdv_StartDT`, `PAdv_EndDT` …",
    ),
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/FACILITYCLOSURE_APPDATA/FeatureServer/0",
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
