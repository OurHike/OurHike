"""Appalachian Mountain Club: places, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Skeptic spot-check: 9, last edit 2024-10-04.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../AMC_Properties_and_Landscapes/FeatureServer/0`: 9 polygons. `AMC_Chapter_Boundaries`. Destination"
        " pages under `/destinations/`.",
    ),
    where=("https://outdoors.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
