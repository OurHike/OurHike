"""National Washington-Rochambeau Revolutionary Route Association: points of interest, published, and
not landed (coverage audit 2026-10-01, batch c11_nht).

"Campsites" are 1781 army encampments, not places to camp. Must not enter POIs as campsites

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/DRAFT_2016_URI_WARO_driving_route_Campsites_web_service`: 120 points; "
        '`…_Historic_Sites_web_service`: 226 (both "DRAFT", edited 2020-07-08)',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://w3r-us.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
