"""Ozark Highlands Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'No OHTA show. Third party: Backpacker Radio #197, "a named individual on Founding the Ozark Highlands '
        'Trail" (2023-04-17); Hike (2020-06-21).',
        "Skeptic: `/wp-json/wp/v2/search?search=podcast` returns `[]`.",
    ),
    where=("https://ozarkhighlandstrail.com/",),
)
