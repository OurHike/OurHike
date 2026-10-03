"""NC High Peaks Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Page/PDF.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/2026Hikes`: 17 group hikes with trail, distance and difficulty. The open-trails table. The "
        "challenge's trail list PDF.",
    ),
    where=("https://nchighpeaks.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
