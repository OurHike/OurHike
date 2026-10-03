"""Ozark Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same blocks:",
        "flood-prone crossings (Bee Fork, Courtois Creek)",
        '"heavy stinging nettle growth"',
        'controlled burns making the trail "hard to follow"',
        '"reports of break-ins to cars parked at the Barton Fen TH"',
        "tornado damage on Victory; Plus the static `/safety-and-guidelines/` page.",
    ),
    where=("https://ozarktrail.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
