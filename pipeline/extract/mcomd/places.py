"""Mountain Club of Maryland: places, drawn from another folder's resource (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'via atc `communities`. Club: `/wp-json/tribe/events/v1/venues` ("Hike Locations") returns 1 venue with no coordinates',
    ),
    where=("https://mcomd.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
