"""Green Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

ATC's reviewed file has 0 VT rows, yet GMC published two A.T. bridge closures on LT/AT miles 64.5
and 75.5 (both since reopened). Skeptic, 2026-10-01: ATC's live page now carries "Vermont: Pomfret
Foliage Road Closure" (`/trail-updates/vermont-pomfret-foliage-road-closure/`), the same event as …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WP REST `https://greenmountainclub.org/wp-json/wp/v2/alert`: 14 items, newest 2026-09-23. Its "
        '`alert-category` taxonomy: "Trail Changes and Closures" 8, "Parking and Trailhead Access Alerts" 4, '
        '"General Guidelines and Seasonal Closures" 3, "Important Alert" 1. Examples: "Taft Lodge Closure '
        'September 8 – end of October", "Seasonal Road Closure: Cloudland Road in Pomfret (Appalachian Trail '
        'Access)", "Now Open: Peru Peak Bridge on LT/AT Mile 64.5". Human page: '
        "`/hike/plan-and-prepare/trail-updates/`. Seasonal guidance: "
        "`/hike/plan-and-prepare/get-started/mud-season/`.",
    ),
    where=(
        "https://greenmountainclub.org/wp-json/wp/v2/alert",
        "https://greenmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
