"""Superior Hiking Trail Association: places, published as a page and a PDF with no coordinate, and not landed
(decision 54, waves 4 and 5, read 2026-10-04). The shuttles page gives the trail's parking rules and links
'Transportation Services for SHT Trail Users' (July 2026), a list of shuttle services, which are businesses
and people, not places; overnight-parking detail is in the paid guidebook (the coverage audit, 2026-10-01).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "superiorhiking.org/robots.txt (Yoast's, `Disallow:` empty), then /shuttles/, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 102,123 bytes, no coordinate in the page; it links "
        "/wp-content/uploads/2026/07/Transportation-Services-for-SHT-Trail-Users-Updated-7.2026.pdf.",
        "the coverage audit (2026-10-01, batch c7_regional_4): /trailheadupdates/ (trailhead renamings) and 6 "
        "/trail-section/ pages with driving directions.",
    ),
    where=("https://superiorhiking.org/shuttles/",),
    reason="needs a per-site reader, not built in this pull request: parking rules in prose; the PDF lists shuttle services, not places",
)
