"""Bay Area Ridge Trail Council: closures, published, and not landed (coverage audit 2026-10-01, batch
p04_persist).

Licence classes: Midpen is none_stated, a disclaimer whose one "may not be used" clause is about
liability, not reuse (quoted in the list at the end). SCC Parks is none_stated (empty licenseInfo;
access "Santa Clara County Parks and Recreation"). The EBRPD page is not GIS, so decision 21(a) does
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Park_Managers` takes 46 values. The largest by miles: Santa Clara County Parks 55.0, EBRPD 52.1, "
        "MROSD 50.2, NPS 31.2, Napa County Regional Parks 22.1, CDPR 21.0. Midpen "
        "`services2.arcgis.com/qmhndvC947rDNl6t/…/Preserve_Access_(public)/FeatureServer/0`: 195 polygons. "
        "`ACCESS='Closed'` 133 (Regular 122, Conservation Management Unit 8, Sensitive 2, Hazardous 1), Open "
        "60, Permit Only 2; edited 2026-07-21. `Trail_(public)/0`: `SEASCLOSE` Yes 31, Unknown 108, No 927; "
        "`TRLACCESS` Permit 10; edited 2026-09-17. Santa Clara County Parks …",
    ),
    where=(
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services",
        "https://ridgetrail.org/",
        "https://ridgetrail.org/{arcgis,server,gis}/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
