"""Palmetto Conservation Foundation: elevation, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Passage page and nav checked.",),
    where=("https://palmettoconservation.org/",),
)
