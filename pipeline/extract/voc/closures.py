"""Volunteers for Outdoor Colorado: closures, nothing published (coverage audit 2026-10-01, batch
p03_persist).

The feed is a blog, not a notices channel.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "New: VOC's real feed is `https://www.voc.org/feed/rss2` (`application/rss+xml`, linked from `/blog`). "
        'It holds 174 items, from 2013-05-07 to 2026-08-20. I scanned every item for "trail closure", "closed '
        'to", "closure", "fire danger", "fire ban", "bear activity", "washout" and "hazard". There were 5 hits,'
        " all incidental, for example \"The Trails Don't Build Themselves: Maintaining Colorado's Iconic 14er "
        'Trails" and "Hanging Lake: Past, Present & Future". Tried: 1–6 as for trail_lines. 7 `/feed`, `/rss`, '
        "`/rss.xml`, `/blog/rss.xml` and `/blog/feed` return 404, and `/blog?format=rss` returns …",
    ),
    where=(
        "https://www.voc.org/feed/rss2",
        "https://voc.org/",
    ),
)
