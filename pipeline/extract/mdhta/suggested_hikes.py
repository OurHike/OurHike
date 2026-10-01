"""Maah Daah Hey Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('19 trail pages (`/trails/`, with distance, campgrounds, overview and "Ideal for").',),
    where=("https://mdhta.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
