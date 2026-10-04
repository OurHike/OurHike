"""Sheltowee Trace Association: places, published as names and a PDF with no coordinate, and not landed (decision
54, waves 4 and 5, read 2026-10-04). The thru-hikers page names five Kentucky-designated trail towns
('Morehead, McKee, Livingston, London, and Stearns') and links the resupply and trail angels PDF, a list of
businesses and people offering help, which nothing here would copy; neither gives a fix.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "sheltoweetrace.org/robots.txt (Squarespace's, our agent allowed), then /thru-hikers, read 2026-10-04 under"
        " lib/user_agent.py's agent: 200, 799,258 bytes, no coordinate in the page; it links "
        "/s/2023_resupply_and_trail_angels.pdf.",
        "the coverage audit (2026-10-01, batch c8_regional_5): /shuttle-services, /passes-and-permits; the resupply"
        " PDF, 154,886 bytes.",
    ),
    where=(
        "https://sheltoweetrace.org/thru-hikers",
        "https://sheltoweetrace.org/s/2023_resupply_and_trail_angels.pdf",
    ),
    reason="needs a per-site reader, not built in this pull request: trail towns named in prose; the resupply PDF lists people and businesses with no coordinate",
)
