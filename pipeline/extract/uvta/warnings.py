"""Upper Valley Trails Alliance: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

See closures.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('The same Trail Finder "Alerts" tab.',),
    where=("https://uvtrails.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
