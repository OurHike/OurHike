"""Sierra Buttes Trail Stewardship: warnings, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

A note follows the status word on the same line, so a parser has to split them. A damaged bridge is
a warning, not a closure, by decision 7, because the trail still reads CLEAR.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.yubaexpeditions.com/trail-conditions`: "Smith Creek Trail CLEAR lower bridge is damaged" '
        '(Mills Peak block, updated 9/4/26). Highway entries note construction delays ("Highway 70 … 30 - 60 '
        'mins delay"). `/fire-hardened-trails` on sierratrails.org describes a project, not a notice.',
    ),
    where=(
        "https://www.yubaexpeditions.com/trail-conditions",
        "https://sierratrails.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
