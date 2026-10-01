"""Palmetto Conservation Foundation: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("33 passage pages: length, difficulty, activities and description.",),
    where=("https://palmettoconservation.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
