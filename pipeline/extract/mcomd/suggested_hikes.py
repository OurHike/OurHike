"""Mountain Club of Maryland: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

Weak: these are trip narratives and events, not curated routes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WP REST category 218 "Mountain Club Of Maryland Hike Reports" (19 posts); '
        "`/wp-json/tribe/events/v1/events` (the dated schedule)",
    ),
    where=("https://mcomd.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
