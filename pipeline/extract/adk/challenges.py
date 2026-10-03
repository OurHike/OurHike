"""Adirondack Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page. The 46ers are a separate org.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/adk-fire-tower-challenge/`: 23 summits (18 of 27 Adirondack plus all 5 Catskill), a patch, proof of stewardship.",
    ),
    where=("https://adk.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
