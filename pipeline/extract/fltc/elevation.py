"""Finger Lakes Trail Conference: elevation, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/elevation-profiles` redirects (301) to `/map/`. Any profile there is the app's widget, not an FLTC dataset.",),
    where=("https://fingerlakestrail.org/",),
)
