"""Green Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The food-storage order is the one ATC lists and drops for having no mile ("Green Mountain NF: Food
Storage", per `atc_updates.json`'s README). GMC states it on its own feed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same endpoint: "Black Bear Activity and Required Food Storage" (modified 2026-08-14), "Notice on '
        "'Trail Magic' Activities in the Green Mountain National Forest\", \"Parking Enforcement on Camel's Hump "
        'Road". Pages: `/hike/plan-and-prepare/staying-safe/food-storage-regulations/`, '
        "`…/wildlife-on-the-trails/`, `…/weather-conditions/`.",
    ),
    where=("https://greenmountainclub.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
