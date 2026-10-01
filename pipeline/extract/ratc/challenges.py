"""Roanoke Appalachian Trail Club: challenges, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

It has the same shape as a section-completion challenge for #1780 — Let a club publish a challenge —
places on its own trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer
Bucket List. The page lists finishers by name, so take the programme only. "Virginia's Triple …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "RATC 113-Mile Club, `https://www.ratc.org/awards/113-mile-club/` (page, modified 2025-04-28): complete"
        " all ~120 mi of RATC's section; honour system; free patch; RATC members only; the checklist is "
        "`/wp-content/uploads/hikes/113-mile-checklist.pdf` (PDF).",
    ),
    where=(
        "https://www.ratc.org/awards/113-mile-club/",
        "https://ratc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
