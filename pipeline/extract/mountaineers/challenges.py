"""The Mountaineers: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Award badges and peak pins at `/membership/badges/award-badges`, e.g. "Seattle Branch Snoqualmie First'
        ' Ten" and "Second Ten" with their peak lists.',
    ),
    where=("https://mountaineers.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
