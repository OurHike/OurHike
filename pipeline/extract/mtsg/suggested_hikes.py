"""Mountains to Sound Greenway Trust: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

HTML bodies come through REST.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WordPress REST `/wp-json/wp/v2/itinerary`: `X-WP-Total` = 28. 9 are typed "Trails, Parks, and '
        'Recreation", e.g. "10 Scenic Middle Fork Hikes Near Seattle That Aren\'t Mailbox Peak or Mount Si" '
        "(2026-04-17). The others are walking tours and scenic drives.",
    ),
    where=("https://mtsgreenway.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
