"""Green Mountain Club: warnings, read with closures (decision 53 phase B, 2026-10-03). closures.py's
notice sources feed this type too: one upstream is one resource and one raw table (decision 34), and
dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Green Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The food-storage order is the one ATC lists and drops for having no mile ("Green Mountain NF: Food
Storage", per `atc_updates.json`'s README). GMC states it on its own feed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same endpoint: "Black Bear Activity and Required Food
Storage" (modified 2026-08-14), "Notice on 'Trail Magic' Activities in the Green Mountain National
Forest", "Parking Enforcement on Camel's Hump Road". Pages:
`/hike/plan-and-prepare/staying-safe/food-storage-regulations/`, `…/wildlife-on-the-trails/`,
`…/weather-conditions/`.

Its `where`: https://greenmountainclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
