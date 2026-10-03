"""AMC Connecticut Chapter: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The verdict holds. The site's ModSecurity answers 406 "Not Acceptable" to a bare `Mozilla/5.0` user
agent or quick requests, so a dlt resource needs a named user agent and a slow rate.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/hiking/hiking-family-hikes/` is guidance for joining led hikes. "Hike Listings" are events.',
        "Skeptic, 2026-10-01: all 97 pages via `/wp-json/wp/v2/pages` (X-WP-Total 97), WP categories (4, all 0 "
        "posts) and `/wp-json/wp/v2/search`. `/nwcamp/rigaplateau/` gives facts about the Riga Plateau (23 "
        "mountains, Bear Mtn 2,316 ft), not a route.",
    ),
    where=("https://ct-amc.org/",),
)
