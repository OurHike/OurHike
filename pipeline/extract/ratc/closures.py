"""Roanoke Appalachian Trail Club: closures, held: www.ratc.org's robots.txt answered 502 to our agent on both
reads of 2026-10-03, which RFC 9309 reads as disallow.

Decision 53's inventory (batch 2) read the club's WordPress REST routes earlier the same day, with a 200
robots.txt that disallowed only /wp-admin/: the Closures category (id 78, 3 posts, newest 'MVP
Construction in Peters Mountain Area', 2023-10-25) is dormant, and closure posts now go untagged to RATC
News (id 13, X-WP-Total 25, newest 2025-11-26 'Catawba Mountain Fire Road Project Complete'). The club
points hikers to Facebook for 'the latest news and alerts', a social channel with no reader here.

In phase B, robots.txt was read again before the first request to the host this session, as every
registration's rule asks, and answered HTTP 502 with an empty body at 22:06 and 22:15 UTC. A host whose
robots.txt fails with a server error is read as refusing (RFC 9309, section 2.3.1.4), so nothing was
fetched and no row was registered. Whether the 502 is RATC's server or the sandbox's proxy failing to
reach it is unknown; one 200 robots.txt read, from a runner or a later session, settles it, and the
two WordpressPosts rows the inventory drafted (`ratc_closures_posts`, `ratc_news_posts`) and the McAfee
Knob page (`ratc_mcafee_page`, WordPress page 2821) can then be registered as drafted. ATC's resources
carry the current A.T. items on RATC's section meanwhile (decision 34).

Before this, the file was the coverage audit's note (confirmed 2026-10-01, batch c3_at_clubs_south),
whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "https://www.ratc.org/robots.txt, read under our agent at 2026-10-03 22:06 and 22:15 UTC (decision 53 "
        "phase B): HTTP 502, empty body, both times. Read as disallow (RFC 9309); nothing else was asked.",
        "(decision 53 inventory, batch 2, earlier on 2026-10-03, robots.txt 200 disallowing /wp-admin/ only) "
        "/wp-json/wp/v2/posts?categories=78: X-WP-Total 3, newest 2023-10-25 (modified 2025-04-26); "
        "categories=13 (RATC News): X-WP-Total 25, newest 2025-11-26.",
        "(coverage audit, 2026-10-01) WP category Closures (id 78, 3 posts: 2022-01-11, 2023-08-21, 2023-10-25), "
        "RSS `https://www.ratc.org/category/closures/feed/`. `/andy-layne-trail/` (page, modified 2026-08-20): "
        '"The new Andy Lane Trail parking lot and permanent reroute is now open", with the Feb 2026 closure '
        'history. The Triple Crown page says "For the latest news and alerts … please check our Facebook page" '
        "(`facebook.com/RoanokeATC`; not fetched).",
    ),
    where=(
        "https://www.ratc.org/robots.txt",
        "https://www.ratc.org/wp-json/wp/v2/posts?categories=78",
        "https://www.ratc.org/wp-json/wp/v2/posts?categories=13",
        "https://www.ratc.org/category/closures/feed/",
        "https://facebook.com/RoanokeATC",
    ),
    reason=(
        "held: the host's robots.txt answered 502 on both of this session's reads, which RFC 9309 reads as "
        "disallow; register the inventory's drafted rows after a 200 read"
    ),
)
