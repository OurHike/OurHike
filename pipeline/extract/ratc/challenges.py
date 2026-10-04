"""Roanoke Appalachian Trail Club: challenges, not read: the host's robots.txt could not be read (decision 54
wave 4, section K, 2026-10-04).

www.ratc.org/robots.txt answered HTTP 502 on 2026-10-04, which RFC 9309 reads as a full disallow, so the 113-Mile
Club's checklist PDF was not fetched. The 113-Mile Club (complete RATC's ~120 miles, members only) is a completion
award in any case.

The note this replaces read, whole:

Roanoke Appalachian Trail Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

It has the same shape as a section-completion challenge for #1780 — Let a club publish a challenge —
places on its own trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer
Bucket List. The page lists finishers by name, so take the programme only. "Virginia's Triple …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): RATC 113-Mile Club, `https://www.ratc.org/awards/113-mile-club/`
(page, modified 2025-04-28): complete all ~120 mi of RATC's section; honour system; free patch; RATC
members only; the checklist is `/wp-content/uploads/hikes/113-mile-checklist.pdf` (PDF).

Its `where`: https://www.ratc.org/awards/113-mile-club/ https://ratc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://www.ratc.org/robots.txt: HTTP 502, 2026-10-04 (RFC 9309: a server error is a full disallow)",),
    where=("https://www.ratc.org/awards/113-mile-club/",),
    reason="not read: robots.txt answered HTTP 502, a full disallow under RFC 9309",
)
