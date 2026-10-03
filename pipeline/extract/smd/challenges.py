"""Save Mount Diablo: challenges, nothing published (coverage audit 2026-10-01, batch c6_regional_3).

Not a place-based challenge.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Mount Diablo Challenge" is a cycling hill climb, and "Diablo Trails Challenge" is a trail race. Both are dated events.',
    ),
    where=("https://savemountdiablo.org/",),
)
