"""AMC Delaware Valley Chapter: podcasts, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Nav and the WP categories ("Book Reviews" are text).',
        "Skeptic: `/videos/` is an empty page, and the WP types hold no podcast type.",
    ),
    where=("https://amcdv.org/",),
)
