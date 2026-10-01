"""Upper Valley Trails Alliance: challenges, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

The passport is "a fitness incentive program designed to keep kids (K-6) outdoors", logging 60
active minutes a day for prizes at 10/20/30 days, mid-January to end of March. It is not tied to any
place or trail, so it does not fit #1780's place-based challenge shape; the Trail Finder badges
remain …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Trail Finder "Earn Badges" (`/earn-badges`: account-based digital badges). uvtrails.org also has a '
        '"Passport to Winter Fun" page.',
    ),
    where=(
        "https://uvtrails.org",
        "https://uvtrails.org/wp-json/wp/v2/pages?slug=passport-to-winter-fun",
        "https://uvtrails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
