"""Ozark Highlands Trail Association: places, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/trail/`: 4 named segments with lengths (Boston Mountains 164 mi, Buffalo River 43, Sylamore 32, "
        "Norfork Lake 72) and the 25 trailheads.",
    ),
    where=("https://ozarkhighlandstrail.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
