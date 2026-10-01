"""AMC Connecticut Chapter: closures, drawn from another folder's resource (coverage audit 2026-10-01,
batch c1_at_clubs_north).

The club defers to ATC in its own words.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://ct-amc.org/trails/` says: "Current closures, trail condition updates and changes to hiker '
        'services in Connecticut are posted … on the Appalachian Trail Conservancy website". '
        "`atc_trail_updates` has 2 CT rows (Limestone Spring Shelter Closed; Macedonia Brook bridge closure and"
        " reroute).",
    ),
    where=(
        "https://ct-amc.org/trails/",
        "https://ct-amc.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
