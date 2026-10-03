"""Old Dominion Appalachian Trail Club: closures, drawn from another folder's resource (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via atc `atc_trail_updates` (0 of 35 entries fall in this section). Club: the `/page-657542` forum's "
        "last trail post is 2018; the maintenance blog `rockfishtoreeds.blogspot.com` (feed: 50 posts) stops at"
        " 2014-01-20",
    ),
    where=("https://rockfishtoreeds.blogspot.com",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
