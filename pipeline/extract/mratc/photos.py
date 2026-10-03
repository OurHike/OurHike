"""Mount Rogers Appalachian Trail Club: photos, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

Rare-plant locations must not be published (see Terms).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Photo1` is populated on 7 of 7 shelters. The rare-plant gallery PDF "
        "(`/_files/ugd/957525_2dbea8ea6ac847bf8a5e682831b12c71.pdf`) is not an open licence.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://mratc.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
