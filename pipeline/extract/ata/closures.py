"""Arizona Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Per-passage categories give each post a location without geocoding. Skeptic spot-check: the RSS
returns 200 `application/rss+xml` with 10 items, the newest titled "UPDATE for Autumn 2026
Thru-Hikers & Riders". WordPress categories confirm `closures-reroutes` (251) = 13.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Category `closures-reroutes` (id 251): 13 posts, 2023-01-15 to 2026-08-31. They include "Arizona Trail'
        ' CLOSED in Grand Canyon" (2026-08-30), "AZT Within Grand Canyon National Park Closed Due to Flooding" '
        '(2026-08-01), "North Kaibab Trail Closes October 15, 2026 for Waterline Project" and "Arizona Trail '
        'Closed for Border Wall Construction" (2026-04-13). RSS '
        "`https://aztrail.org/category/closures-reroutes/feed/`. REST `/wp-json/wp/v2/posts?categories=251`. "
        "There are also `passage-updates` (11) and per-passage categories.",
    ),
    where=(
        "https://aztrail.org/category/closures-reroutes/feed/",
        "https://aztrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
