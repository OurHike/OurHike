"""Waldo County Trails Coalition: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Section guides in PDF form.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("6 sections with mileage on `/maps`, and `/activities`.",),
    where=(
        "https://www.hillstosea.org/maps",
        "https://www.hillstosea.org/closures",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
