"""Maine Appalachian Trail Club: photos, drawn from another folder's resource (coverage audit
2026-10-01, batch c1_at_clubs_north).

ATC permission, not an open licence.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Photo1` is populated on 32 of 34 MATC shelters in ATC layer 4; `fetch_atc_photos.py` reads them. "
        'MATC\'s own "Photo Upload & Gallery" page (`/alpha-form-test-page/`) states no licence.',
    ),
    where=("https://matc.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
