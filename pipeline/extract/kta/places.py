"""Keystone Trails Association: places, published as prose pages with no coordinate, and not landed (decision 54,
wave 5, read 2026-10-04). The 'Find a Trail' pages (28 in the sitemap) describe each trail ('73.7-mile ...
loop', 'main trailhead is at Parker Dam State Park', Quehanna's) with no fix. KTA's own GPS data is on
CalTopo, whose robots.txt refuses its data route (kta/points_of_interest.py).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "kta-hike.org/robots.txt (/ajax/ and /apps/ disallowed), then /quehanna-trail.html, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 124,182 bytes, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c1_at_clubs_north): 28 trail pages (`-trail.html`, "
        "`trail-system.html`) and hiking-clubs.html, a club directory.",
    ),
    where=(
        "https://kta-hike.org/quehanna-trail.html",
        "https://kta-hike.org/",
    ),
    reason="needs a per-site reader, not built in this pull request: trail pages in prose with no coordinate",
)
