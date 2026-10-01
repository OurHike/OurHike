"""Tennessee Eastman Hiking & Canoeing Club: photos, drawn from another folder's resource (coverage
audit 2026-10-01, batch c3_at_clubs_south).

Not openly licensed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`Photo1` is populated on 15 of 15 shelters. The wiki has 1,127 files and an empty `rightsinfo`.",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://tehcc.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
