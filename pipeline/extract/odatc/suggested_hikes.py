"""Old Dominion Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Only the Albright Trail is the club's own.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/page-1503143` (page): 2 circuit hikes. For Humpback Rocks, the description and map are third-party "
        "(`hikingupward.com`); for the Albright Trail, ODATC's own PDF map",
    ),
    where=("https://hikingupward.com",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
