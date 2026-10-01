"""Connecticut Forest & Park Association: challenges, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

A mileage challenge rather than a place list. It fits #1780's model less well. Skeptic spot-check:
the challenge page returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://ctwoodlands.org/explore-trails/blue-blazed-hiking-trails-challenge/`: 50, 200, 400 and "
        "800-mile categories (patch, bottle, beanie, vest), with an Excel or Google Sheets mileage log. Also "
        "the NET Hike Challenge 2026 (`newenglandtrail.org/hike-50-challenge/`), run jointly with AMC.",
    ),
    where=(
        "https://ctwoodlands.org/explore-trails/blue-blazed-hiking-trails-challenge/",
        "https://newenglandtrail.org/hike-50-challenge/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
