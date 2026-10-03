"""Bartram Trail Conference: photos, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('BRBTC `/gallery/` and the BTC "Marker Photos" and "Conference Photographs" pages carry no open licence.',),
    where=("https://bartramtrail.org/",),
)
