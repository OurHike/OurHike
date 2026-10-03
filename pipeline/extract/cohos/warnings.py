"""The Cohos Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/trouble-spots/` (2026-07-13): "LOGGING. Active logging can pose an extreme hazard to a hiker", by location.',),
    where=("https://cohostrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
