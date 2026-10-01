"""Tidewater Appalachian Trail Club: challenges, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Cabin Incentive Program" PDF: an early-reservation perk for volunteers on cabin work trips, not a hiker challenge.',
        "Skeptic: the WooCommerce store (`/wp-json/wc/store/v1/products`) has 8 donation funds, among them "
        '"Awards Program" ("the yearly TATC Awards Program"). A WP search for "award" hits only Timekeeping '
        "(volunteer hours) and a FOFCSP state-parks award",
    ),
    where=("https://tidewateratc.org/",),
)
