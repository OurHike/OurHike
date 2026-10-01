"""Ozark Highlands Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

The machine-readable route to the live page is `/wp-json/wp/v2/pages?slug=trail-alerts`, which
carries a `modified` date. The category feed is stale. Skeptic, re-read 2026-10-01: `modified` is
still 2026-09-21, and both items are present. The page embeds the USFS "East Fly Gap Road closure
Map.jpg" …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/trail-alerts/` (WP page, `modified` 2026-09-21): "The bridge over Big Piney Creek (mm 103.9) is '
        'closed for a rehabilitation project. Work is expected to continue until December 3, 2026"; "Fort '
        'Douglas trailhead (mm 103.7) … may be inaccessible"; "East Fly Gap Road is closed … due to a '
        'landslide". The WP category "Trail Alerts" (id 18) has 14 posts, newest 2022-03-04, with RSS at '
        "`/category/trailalerts/feed/`.",
    ),
    where=("https://ozarkhighlandstrail.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
