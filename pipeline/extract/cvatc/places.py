"""Cumberland Valley Appalachian Trail Club: places, drawn from another folder's resource (coverage
audit 2026-10-01, batch c2_at_clubs_mid).

Scott Farm is not built yet, so it is a place to record later, not now.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via atc `communities` (Boiling Springs). Club news: Scott Farm, to become a visitor center and KTA HQ "
        'with "a water filling station" (2026-09-03)',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://cvatclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
