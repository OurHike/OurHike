"""Trailkeepers of Oregon: closures, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Use REST `modified`, not the RSS feed. `/category/trail-conditions/feed/` reports the 2025 publish
dates, so it cannot tell when a post changed. The page says TKO staff update it and FarOut "as soon
as possible".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "OCT Trail Conditions, WordPress REST "
        '`https://trailkeepersoforegon.org/wp-json/wp/v2/posts?categories=10`. Two posts: "Recent Updates" (id '
        '3502, modified 2026-08-25) and "Additional Updates" (id 3573, modified 2026-08-31). They are shown '
        "together on `/trail-conditions/`. Current items: a landslide closing the trail down the south side of "
        'Tillamook Head, the North Rainforest Trail at Cascade Head "effectively closed", the trail up Cape '
        'Meares closed by a landslide, North Cape Sebastian "washed out at Daniels Creek … Do not attempt", '
        "Cape Lookout SP campground closed, Necarney Creek bridge out. …",
    ),
    where=(
        "https://trailkeepersoforegon.org/wp-json/wp/v2/posts?categories=10",
        "https://trailkeepersoforegon.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
