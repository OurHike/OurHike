"""Mazamas: elevation, nothing published (coverage audit 2026-10-01, batch c6_regional_3).

Elevation gain is a column on the hike list (below), not an elevation product.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same.",),
    where=("https://mazamas.org/",),
)
