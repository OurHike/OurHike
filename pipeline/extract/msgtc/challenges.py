"""Monadnock-Sunapee Greenway Trail Club: challenges, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Thin: a patch, no application.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/store/`: an "END to END" rocker patch, $5.',),
    where=("https://msgtc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
