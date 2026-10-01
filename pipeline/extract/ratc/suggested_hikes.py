"""Roanoke Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

CalTopo LineStrings plus page text make this the most structured hike set in the batch after
TEHCC's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/at-hiking/ratcs-14-at-hikes/` (page, modified 2026-06-11): 14 hikes covering the whole section, with"
        " length (5.5–13.2 mi) and difficulty. Trailhead coordinates are in Google Maps `daddr=` links, and "
        "routes are in the CalTopo `8AEHQUP` JSON (machine-readable). `/at-hiking/113-mile-hike-list/` "
        "(2023-03-29) gives the same hikes with gain/loss, directions and 11 per-hike map PDFs. Also "
        "`/wp-content/uploads/hikes/top-10-day-hikes-in-VA.pdf`.",
    ),
    where=("https://ratc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
