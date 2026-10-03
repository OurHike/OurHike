"""Roanoke Appalachian Trail Club: closures, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

The feed is dormant since 2023, and ATC carries the current items (6 rows on RATC's section, above).
The Facebook channel is UNKNOWN and probably the live one. (skeptic: the category is dormant, the
club is not.) Closure posts now go to "RATC News" (id 13) without the Closures tag: "Catawba …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WP category Closures (id 78, 3 posts: 2022-01-11, 2023-08-21, 2023-10-25), RSS "
        '`https://www.ratc.org/category/closures/feed/`. `/andy-layne-trail/` (page, modified 2026-08-20): "The'
        ' new Andy Lane Trail parking lot and permanent reroute is now open", with the Feb 2026 closure '
        'history. The Triple Crown page says "For the latest news and alerts … please check our Facebook page" '
        "(`facebook.com/RoanokeATC`; not fetched).",
    ),
    where=(
        "https://www.ratc.org/category/closures/feed/",
        "https://facebook.com/RoanokeATC",
        "https://ratc.org/",
        "https://www.ratc.org/feed/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
