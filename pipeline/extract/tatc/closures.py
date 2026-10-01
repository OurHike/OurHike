"""Tidewater Appalachian Trail Club: closures, drawn from another folder's resource (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via atc `atc_trail_updates` (0 entries in section). Club publishes none.",
        'Skeptic: `/feed/` is empty (843 bytes, 0 posts, one category "Uncategorized", count 0). The Aug–Sep '
        "2026 newsletter (`NewsletterAug26Sep26.pdf`, 4.3 MB) holds work-trip reports and no closure",
    ),
    where=("https://tidewateratc.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
