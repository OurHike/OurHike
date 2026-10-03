"""Ozark Highlands Trail Association: challenges, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'FAQ: "Is there a trail patch available? Yes. There is an eight color cloth patch … for sale for $4". '
        "That is a souvenir, not a completion award. No end-to-end programme in the 17 pages, 7 categories or "
        "the FAQ.",
        "Skeptic, verdict upheld:",
        '`/wp-json/wp/v2/search` for "challenge" returns nothing.',
        '"end-to-end" hits only the FAQ (`modified` 2026-09-30), where it is about water and duration: "A '
        'complete thru hike is difficult but possible…".',
        '"patch" hits the store\'s "OHT Patch" product and the FAQ answer above.',
        '"certificate" hits only "Get Involved"\'s Temporary Membership Certificate for …',
    ),
    where=("https://ozarkhighlandstrail.com/",),
)
