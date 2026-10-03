"""Pacific Northwest Trail Association: challenges, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Do not load the finishers list. Skeptic spot-check: `/1200-milers/` returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/pnta/know-before-you-go/1200-milers/` ("Register as a 1,200 Miler") and `/pnt-finishers/`.',),
    where=("https://pnt.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
