"""Adirondack Mountain Club: places, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Pages; gated by terms.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/explore/adk-loj-property/`, `/explore/high-peaks-information-center/`, "
        "`/explore/johns-brook-lodge/`, `/tips-for-hiker-parking-adirondak-loj/`.",
    ),
    where=("https://adk.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
