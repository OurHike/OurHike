"""Keystone Trails Association: closures, refused by CalTopo's robots.txt (decision 53, phase B, 2026-10-03).

The one closure fact KTA publishes is a marker on its CalTopo trail maps, and those maps' data comes
only from CalTopo's `/api/`, which caltopo.com's robots.txt disallows for every agent, ours included.
So it is not fetched, and the route forward is permission (KTA's, or CalTopo's for an export), which
the maintainer asks for, or KTA republishing the fact on its own site. KTA's news feed (Weebly RSS)
carries articles, not notices: its 2025 hunting-Sundays post is expired, and the Pennsylvania Game
Commission is the authority for that (the decision 53 inventory, batch 5).

The coverage audit's note (2026-10-01): a closure fact buried in map markers, needing a rule for
which markers are hazards (@unvalidated). On the A.T., ATC's own resources cover KTA's section (1
Outerbridge bear warning). The audit's skeptic found this the only hazard marker in all 6 maps.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "caltopo.com/robots.txt, read 2026-10-03 under lib/user_agent.py's agent: `User-agent: *` then "
        "`Disallow: /api/` among ten Disallow lines; the map's data URL `/api/v1/map/28V9AS6/since/0` falls "
        "under it, so it was not requested (the decision 53 inventory, batch 5, read the same rule).",
        '(coverage audit, 2026-10-01) The Quehanna CalTopo map carries a marker titled "Corporation Dam (bridge '
        "out as of 2025)\". There is no closures page: `news.html` is the president's letter, and "
        "`report-a-trail-issue.html` is a form.",
        "(the inventory, 2026-10-03) `https://www.kta-hike.org/news/feed`: Weebly RSS, 11,967 B, no ETag and a "
        "Last-Modified equal to the request time; articles, no notices.",
    ),
    where=(
        "https://caltopo.com/robots.txt",
        "https://www.kta-hike.org/maps.html",
        "https://www.kta-hike.org/news/feed",
        "https://kta-hike.org/",
    ),
    terms="caltopo.com/robots.txt (read 2026-10-03): `User-agent: *` / `Disallow: /api/`",
    reason="refused: robots.txt disallows the only machine-readable path for every agent; held until KTA or CalTopo permits",
)
