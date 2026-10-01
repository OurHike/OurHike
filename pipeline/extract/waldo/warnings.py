"""Waldo County Trails Coalition: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

One page feeds both marts.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('The same page\'s "Hunting Seasons" section, plus "Wear orange during hunting season" on the maps.',),
    where=(
        "https://www.hillstosea.org/maps",
        "https://www.hillstosea.org/closures",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
