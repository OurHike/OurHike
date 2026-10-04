"""Upper Valley Trails Alliance: challenges, badges inside an account, and not landed (decision 54 wave 5,
section K, 2026-10-04).

Trail Finder's 'Earn Badges' are digital badges kept in a hiker's account, another site's; the 'Passport to Winter
Fun' is a seasonal page. uvtrails.org's robots.txt asks `Crawl-delay: 60`. No request sent today.

The note this replaces read, whole:

Upper Valley Trails Alliance: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

The passport is "a fitness incentive program designed to keep kids (K-6) outdoors", logging 60 active
minutes a day for prizes at 10/20/30 days, mid-January to end of March. It is not tied to any place or
trail, so it does not fit #1780's place-based challenge shape; the Trail Finder badges remain …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Trail Finder "Earn Badges" (`/earn-badges`: account-based digital
badges). uvtrails.org also has a "Passport to Winter Fun" page.

Its `where`: https://uvtrails.org https://uvtrails.org/wp-json/wp/v2/pages?slug=passport-to-winter-fun
https://uvtrails.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) Trail Finder /earn-badges, account-based",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://uvtrails.org/",),
    reason="not published as a page: badges inside an account on another site",
)
