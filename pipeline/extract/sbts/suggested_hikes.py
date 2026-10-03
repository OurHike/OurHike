"""Sierra Buttes Trail Stewardship: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

Bikepacking-first, though the page names hikers too. Skeptic:
`https://www.yubaexpeditions.com/trail-routes` lists the Mt. Hough "Signature Routes" with length,
descent and climb, e.g. "Mt. Hough Trail … Length -11 Miles Descent - 4000 feet Climbing - 200
feet". They are shuttle laps written for …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/connected-communities-routes`, plus three route pages: "
        "`/lost-sierra-adventures-bikepacking-the-lost-sierra-loop/`, "
        "`/bikepacking-the-lost-sierra-sagebrush-to-snowbanks/` and "
        "`/bikepacking-the-sierra-buttes-lost-sierra-high-line/`. HTML.",
    ),
    where=(
        "https://www.yubaexpeditions.com/trail-routes",
        "https://sierratrails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
