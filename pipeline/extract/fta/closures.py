"""Florida Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

The categories mix closures with Notices to Hikers ("NTH"). By decision 7, an unclassified row goes
to warnings. Post titles carry FTA map-sheet numbers ("Maps 39-40"), not coordinates. Skeptic:
spot-checked `X-WP-Total: 14` for those five categories. The per-category counts add to 15, so one
post …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WordPress REST `https://floridatrail.org/wp-json/wp/v2/posts?categories=37,40,41,42,43`: categories "
        "`closures-notice-to-hikers-general` (2), `closures-and-nth-panhandle` (3), `-north` (5), `-central` "
        '(1), `-south` (4). 14 posts, 2018-07-01 to 2026-07-28 (newest: "Map 14 – Sugar Creek Closure along '
        'Suwannee River"). There is an RSS feed per category, e.g. '
        "`https://floridatrail.org/category/closures-and-nth-north/feed/` (200, `application/rss+xml`). The 3 "
        "`Open_Statu = Closed` segments above are a machine-readable closure.",
    ),
    where=(
        "https://floridatrail.org/wp-json/wp/v2/posts?categories=37,40,41,42,43",
        "https://floridatrail.org/category/closures-and-nth-north/feed/",
        "https://floridatrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
