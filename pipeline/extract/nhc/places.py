"""Nantahala Hiking Club: places, published as a page and a PDF with no coordinate, and not landed (decision 54,
waves 4 and 5, read 2026-10-04). The thru-hiker page names Franklin as the first A.T. Community and Macon
County Transit's shuttles 'to and from Winding Stair Gap and Deep Gap three times a day, Monday through
Friday'; the SOBO-by-Sections PDF names 23 maintenance-section points with miles, NOC to the GA/NC line (the
coverage audit, 2026-10-01). Neither gives a fix; ATC's `communities` places Franklin.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "www.nantahalahikingclub.org/robots.txt (Yoast's, `Disallow:` empty), then /thru-hiker/, read 2026-10-04 "
        "under lib/user_agent.py's agent: 200, 138,112 bytes, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c3_at_clubs_south): /wp-content/uploads/2025/10/SOBO-by-Sections.pdf"
        " (2025-10-15), 23 points with miles.",
    ),
    where=(
        "https://www.nantahalahikingclub.org/thru-hiker/",
        "https://www.nantahalahikingclub.org/wp-content/uploads/2025/10/SOBO-by-Sections.pdf",
    ),
    reason="needs a per-site reader, not built in this pull request: a trail town and section points named with miles and no coordinate",
)
