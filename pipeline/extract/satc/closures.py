"""Susquehanna Appalachian Trail Club: closures, drawn from another folder's resource (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("via atc `atc_trail_updates`. SATC's own `/a-t-alerts.html` is only a link to ATC Trail Updates",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://satc-hike.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
