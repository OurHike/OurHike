"""Green Mountain Club: places, published as pages with no fix of the club's own, and not landed (decision 54,
wave 5, read 2026-10-04). The visitor center pages give addresses and Google Maps links, Google's places
rather than the club's fixes; the End-to-Ender's Guide (trail towns and amenities) is behind an e-mail form.
The club's `PARKING_MASTER` (96 named trailheads) is an ArcGIS layer, wave 1's reader, and the lead's to
route. A.T. towns in Vermont arrive through ATC's `communities`; Long Trail towns do not.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "greenmountainclub.org/robots.txt (Yoast's, a `Crawl-delay: 10` above every group, honoured), then "
        "/about/visitor-centers/gmc-visitor-center/, read 2026-10-04 under lib/user_agent.py's agent: 200, 194,774 "
        "bytes, 4 Google Maps links and no coordinate of the club's own.",
        "the coverage audit (2026-10-01, batch c1_at_clubs_north): the three visitor centres; PARKING_MASTER; the "
        "guide behind an e-mail form.",
    ),
    where=("https://greenmountainclub.org/about/visitor-centers/gmc-visitor-center/",),
    reason="needs a per-site reader, not built in this pull request: visitor centres given as addresses and Google links; the parking layer is ArcGIS, the lead's",
)
