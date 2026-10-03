"""Randolph Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

PDF; route lines would need the trail network.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://randolphmountainclub.org/wp-content/uploads/Recommended-Hikes-1.pdf` (PDF, 104,747 bytes, "
        "last-modified 2023-02-20).",
    ),
    where=("https://randolphmountainclub.org/wp-content/uploads/Recommended-Hikes-1.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
