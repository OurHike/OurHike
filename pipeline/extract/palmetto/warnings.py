"""Palmetto Conservation Foundation: warnings, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/updates/post/hunting-season` (2025-12-11): season late August to early March, wear blaze orange, "
        'links to SC regulations. Each passage has a "Trail on Hunting Grounds" field and Trail Alerts.',
    ),
    where=("https://palmettoconservation.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
