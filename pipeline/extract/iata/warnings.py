"""Ice Age Trail Alliance: warnings, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

"High Water" and "Trail Flooded" are warnings, not drought (decision 2). Skeptic spot-check:
`IATA_Lands_Hunting_Regulations_view/9` = 65, last edit 2026-07-13.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same conditions layer\'s non-closure headings: "Caution - Logging Activities" 5, "Caution - logging'
        ' near trail" 3, High Water 3, Storm Damage 3, Trail Flooded 2, Confusing blazes 2, hornet nests 2, '
        '"New Wood River - dangerous ford" 1. `.../IATA_Lands_Hunting_Regulations_view/FeatureServer/9`: 65 '
        "polygons. `.../IAT_Dogs_Prohibited`: 7 lines plus 6 points. Page "
        "`iceagetrail.org/explore/plan-hike/hunting-season-iata/` (blocked by robots.txt).",
    ),
    where=("https://iceagetrail.org/explore/plan-hike/hunting-season-iata/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
