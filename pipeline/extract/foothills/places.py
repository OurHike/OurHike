"""Foothills Trail Conservancy: places, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/nearby-state-parks/` lists 7 SC state parks. `/registration/` lists 3 registration kiosks (Table "
        "Rock SP, Oconee SP, Frozen Creek at Gorges SP) and parking fees ($5/day Oconee, $6/day Table Rock, "
        "$2/day USFS Whitewater Falls). Both are pages.",
    ),
    where=("https://foothillstrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
