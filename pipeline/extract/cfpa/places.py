"""Connecticut Forest & Park Association: places, published as a list with no geometry, and not landed (decision
54, wave 5, read 2026-10-04). The properties page lists CFPA's protected properties by name, with no boundary
or fix; the park each Blue-Blazed trail sits in rides on the trail lines as `Par_Name` (the coverage audit,
2026-10-01), which CFPA's loaded trail layer carries.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "ctwoodlands.org/robots.txt (`Crawl-delay: 10`, honoured), then /properties/, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 93,138 bytes, no coordinate and no linked GIS file in the page.",
        "the coverage audit (2026-10-01, batch c10_nst_rest): /properties/ answered 200; `Par_Name` on every trail line.",
    ),
    where=("https://ctwoodlands.org/properties/",),
    reason="needs a per-site reader, not built in this pull request: the properties are named, with no boundary or coordinate",
)
