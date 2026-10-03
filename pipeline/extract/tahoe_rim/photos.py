"""Tahoe Rim Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Points_of_Interest.PhotoURL` is filled on 0 of 228 rows and `Vistas.Photo_URL` on 0 of 297. "
        "`/trta-photo-contest/` states no licence.",
    ),
    where=("https://tahoerimtrail.org/",),
)
