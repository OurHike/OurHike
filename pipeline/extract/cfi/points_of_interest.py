"""Colorado Fourteeners Initiative: points of interest, published with no coordinate, and not landed (decision
54, wave 5, read live 2026-10-04).

Each of the 53 peak pages gives the summit's height and rank (Mount Bierstadt: "14,065 feet (38th highest)")
and names its recommended trailhead in prose, with no coordinate for either. A summit or a trailhead is never
looked up from its name, so nothing places them here; USGS's GNIS summits and USFS's trailheads, which other
folders load, hold the same features with fixes.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt on 14ers.org and www.14ers.org (`Disallow: /wp-admin/` only, no Crawl-delay), then "
        "/peaks/front-range/mount-bierstadt/, read 2026-10-04 under lib/user_agent.py's agent: 200, 233,126 "
        "bytes, '14,065 feet (38th highest)', a route description, and no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c5_regional_2): 53 peak pages under `/peaks/<range>/<peak>/`, "
        "counted from `wp-sitemap-posts-page-1.xml`; no coordinates on the sampled pages.",
    ),
    where=("https://www.14ers.org/peaks/front-range/mount-bierstadt/", "https://14ers.org/"),
    reason="published with no coordinate: heights and trailhead names in prose, never geocoded",
)
