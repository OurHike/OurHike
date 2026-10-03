"""Lewis and Clark Trust: points of interest, published, and not landed (coverage audit 2026-10-01,
batch p10_persist).

All four items: licenseInfo "The National Park Service shall not be held liable for improper or
incorrect use of the data described and/or contained herein…", a disclaimer on a federal work, so
public domain. The Bergantino item's accessInformation also credits "a named individual, Montana
Bureau …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'NPS org `fBc8EJBxQRMcHlei`, LECL layers: "LECL Lewis and Clark Trail Visitor Centers and Museums" '
        "`https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/Lewis_and_Clark_Trail_Visitor_Centers_and_Museums/FeatureServer/0`"
        " (item `d234be9257b84fea91666c9c4c52b9c9`): 172 points, last edit 2025-04-21, fields `SITE_NAME`, "
        '`STREET_ADD`, `SITE_TYPE`, `HPHS`, `URL`. "LECL Lewis and Clark NHT High Potential Historic Sites" '
        "`…/HPHS/FeatureServer/0` (`Cultural_HPHS_nonsensitive`, item `d3cb1870cd244ec1b1871d80371b1e70`): 93 "
        'points, last edit 2026-03-02. "LECL Pivotal Places" …',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/Lewis_and_Clark_Trail_Visitor_Centers_and_Museums/FeatureServer/0",
        "https://lewisandclark.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
