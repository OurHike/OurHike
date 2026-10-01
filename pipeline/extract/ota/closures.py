"""Ozark Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Pages. No feed: `posts` holds 13 items in 4 categories, none of them conditions.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Trail Conditions" blocks on 13 of the 14 section pages (all read):',
        'Current River: "Midco Hollow south to Pike Creek Road—will remain closed due to unprecedented tornado damage" (4/2025)',
        'Upper Current: "The western leg of the Brushy Creek Trail is closed until further notice" (1/2026)',
        "Peck Ranch: closes seasonally for deer season and elk calving",
        'Between the Rivers: "US Forest Service gates will close for spring firearms turkey season"; Section '
        "pages are reached as `https://ozarktrail.com/?page_id=42254` and similar.",
    ),
    where=("https://ozarktrail.com/?page_id=42254",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
