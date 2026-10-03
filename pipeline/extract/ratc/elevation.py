"""Roanoke Appalachian Trail Club: elevation, nothing published (coverage audit 2026-10-01, batch
c3_at_clubs_south).

USGS 3DEP (`_shared/`) covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Nav, the WP page list and search. No DEM or profile. The per-hike "Elevation Gain/(Loss): '
        '1,000/(1,000)" lines on `/at-hiking/113-mile-hike-list/` belong with suggested_hikes.',
    ),
    where=("https://ratc.org/",),
)
