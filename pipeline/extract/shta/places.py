"""Superior Hiking Trail Association: places, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages/PDF. Overnight-parking detail is in the paid guidebook.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/shuttles/` (parking rules, 4+ shuttle services) and the PDF "
        "`wp-content/uploads/2026/07/Transportation-Services-for-SHT-Trail-Users-Updated-7.2026.pdf`. Also "
        "`/trailheadupdates/` (the trailhead renamings), and 6 `/trail-section/` pages with trailhead driving "
        "directions.",
    ),
    where=("https://superiorhiking.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
