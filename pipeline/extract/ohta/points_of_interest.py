"""Ozark Highlands Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

Page; the WordPress page JSON is at `/wp-json/wp/v2/pages?slug=trail`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/trail/`: 25 "Major trail heads" with mileposts and decimal coordinates, e.g. "Lake Ft Smith (mile '
        '0): 35.694624, -94.11849". FAQ: 14 named public campgrounds; water ("In the drier months (July – '
        'September) the water can be hard to find … stash some water").',
        "Skeptic, count corrected upward: the page JSON (`modified` 2026-09-10) holds 41 decimal coordinate "
        "pairs, about 38 distinct points. The Boston Mountains, Buffalo River and Sylamore blocks carry 25 "
        'mileposted trailheads plus side "Parking at …" points. The Norfork Lake block adds 13 access points '
        "with no mileposts (Norfork Dam/Quarry …",
    ),
    where=("https://ozarkhighlandstrail.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
