"""Blue Mountain Eagle Climbing Club: places, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

The 18 hospital ERs bear on getting off the trail quickly. No other source in this batch publishes
them.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'KML folders "Hospital Emergency Rooms" (18) and "Access Points" (7). `/bmecc-membership/properties` '
        '(page): Rentschler Arboretum, 34 acres owned by the club, "open to the public during daylight hours". '
        "Trail towns LOADED via atc `communities`",
    ),
    where=("https://bmecc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
