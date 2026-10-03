"""Maine Appalachian Trail Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The ferry warning is permanent and fatal-grade. `atc_trail_updates` does not carry it (settled by
skeptic): ATC's trail updates are the WordPress subtype `trail-updates`, and a search of
`https://appalachiantrail.org/wp-json/wp/v2/search?search=Kennebec` returns 11 pages and posts (e.g.
"River & …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.matc.org/kennebec-river-ferry-service/` (page): the 2026 ferry schedule (May 22–Jun 30 "
        "9–11 a.m.; Jul 1–Sep 30 9 a.m.–2 p.m.) and \"Do not attempt to wade or swim across Maine's Kennebec "
        'River … Two hikers are known to have died attempting to ford the river." Also the WordPress category '
        "Hazard (id 157, 2 posts, both 2023-09-14) at `/wp-json/wp/v2/posts?categories=157`, with an RSS feed "
        "at `/category/hazard/feed/`.",
    ),
    where=(
        "https://www.matc.org/kennebec-river-ferry-service/",
        "https://appalachiantrail.org/wp-json/wp/v2/search?search=Kennebec",
        "https://matc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
