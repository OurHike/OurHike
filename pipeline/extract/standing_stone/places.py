"""Standing Stone Trail Club: places, published as section names with no coordinate, and not landed (decision 54,
wave 5, read 2026-10-04). The trail sections page names 34 maintenance sections by their endpoints and
lengths, with no fix; the two trail towns in the Sweet 16 (Three Springs, Mapleton Depot) and the termini on
/trail-guides are prose too (the coverage audit, 2026-10-01).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "www.standingstonetrail.org/robots.txt (Wix's), then /trail-sections, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 871,443 bytes, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c8_regional_5): 34 maintenance sections with named endpoints and lengths.",
    ),
    where=("https://www.standingstonetrail.org/trail-sections",),
    reason="needs a per-site reader, not built in this pull request: sections named by their endpoints, with no coordinate",
)
