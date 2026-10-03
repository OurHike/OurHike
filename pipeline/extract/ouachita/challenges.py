"""Friends of the Ouachita Trail: challenges, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'REST searches `patch` and `thru-hike` return only the "FoOTnotes 2020" newsletter and "Outside Links".',
        "Skeptic: `/store/` (modified 2025-07-10) sells only bandanas and T-shirts, through Mountain Valley "
        "Spring Water. There is no completion patch, and no finisher page among the 49 sitemap pages.",
    ),
    where=("https://friendsoftheouachita.org/",),
)
