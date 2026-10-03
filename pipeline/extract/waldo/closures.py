"""Waldo County Trails Coalition: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page. Safety-relevant now: several closures start late September or Oct 3.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.hillstosea.org/closures`: "Hogback Mountain section is closed until further notice", plus'
        ' dated 2026 hunting closures per town (e.g. "Closed from Oct 3 thru Dec 12 (Closure includes '
        'Sundays)").',
    ),
    where=("https://www.hillstosea.org/closures",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
