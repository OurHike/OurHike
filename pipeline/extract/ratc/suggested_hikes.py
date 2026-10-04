"""Roanoke Appalachian Trail Club: suggested hikes, pages and PDFs (waves 4 and 5) and a CalTopo map
refused by its host's robots.txt (decision 54 wave 3, section C, 2026-10-04).

The routes sit in a CalTopo map (`8AEHQUP`), whose data comes only from caltopo.com/api/, which
caltopo.com's robots.txt disallows for every agent (`User-agent: *` / `Disallow: /api/`, decision
53's inventory, 2026-10-03). The 14 A.T. hikes and the 113-mile list are pages, and the 11 map PDFs
and the top-10 list PDFs, waves 4 and 5, named in section C's hand-back.

The note this replaces read, whole:

Roanoke Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

CalTopo LineStrings plus page text make this the most structured hike set in the batch after
TEHCC's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "caltopo.com's robots.txt as decision 53's inventory quoted it (batch 3, 2026-10-03): `Disallow: /api/` under `User-agent: *`; nothing was asked today.",
        "(the coverage audit, 2026-10-01) `/at-hiking/ratcs-14-at-hikes/` (page, modified 2026-06-11): 14 hikes covering the whole section, with length (5.5–13.2 mi) and difficulty. Trailhead coordinates are in Google Maps `daddr=` links, and routes are in the CalTopo `8AEHQUP` JSON (machine-readable). `/at-hiking/113-mile-hike-list/` (2023-03-29) gives the same hikes with gain/loss, directions and 11 per-hike map PDFs. Also `/wp-content/uploads/hikes/top-10-day-hikes-in-VA.pdf`.",
    ),
    where=(
        "https://caltopo.com/robots.txt",
        "https://ratc.org/",
    ),
    terms="robots.txt: `Disallow: /api/` (caltopo.com, for every agent)",
    reason="the routes are refused by CalTopo's robots.txt; the hike list is a page and PDFs, waves 4 and 5",
)
