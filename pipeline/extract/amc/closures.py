"""Appalachian Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

All page or PDF. AMC publishes no trail-closure feed for the Whites. Those closures come from WMNF
(`usfs` folder). Skeptic spot-check: `newenglandtrail.org/closures-notices/` returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://newenglandtrail.org/closures-notices/`, Massachusetts: 4 notices, 3 of them parking closures "
        "in Section 16 (Erving). `https://www.outdoors.org/weather-trail-conditions/`: an Open/Closed `Status` "
        "per hut and lodge. The AMC Book Updates PDF, `cdn.outdoors.org/.../AMC_BookUpdates_10.30.24_v2.pdf`, "
        "lists trail relocations as of 2024-10-30.",
    ),
    where=(
        "https://newenglandtrail.org/closures-notices/",
        "https://www.outdoors.org/weather-trail-conditions/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
