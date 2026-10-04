"""Benton MacKaye Trail Association: places, published as names with no area or fix, and not landed (decision 54,
wave 5, read 2026-10-04). The Trail Town Communities page names three designated towns (Blue Ridge and Fannin
County, Ellijay and Gilmer County, Tellico Plains and Monroe County) in prose, and the Thru-Hikers' Guide
lists lodging, food, post offices and shuttles by mile (the coverage audit, 2026-10-01). A town is never
looked up from its name; ATC's `communities` places the A.T.'s, and the three BMT towns would need a fix a
person reviews.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "bmta.org/robots.txt (Flywheel's, `Crawl-delay: 60`, honoured), then /trail-town-communities/, read "
        "2026-10-04 under lib/user_agent.py's agent: 200, 110,671 bytes, the three towns in prose, no coordinate in"
        " the page.",
        "the coverage audit (2026-10-01, batch c8_regional_5): /thru-hikers-guide/#resupply, from mile 18.5 to 286.2.",
    ),
    where=(
        "https://bmta.org/trail-town-communities/",
        "https://bmta.org/thru-hikers-guide/",
    ),
    reason="needs a per-site reader, not built in this pull request: three trail towns named in prose, with no area or coordinate",
)
