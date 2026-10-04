"""National Park Service (points of interest): challenges, drawn from nps/challenges.py's
`nps_passport_stamp_locations` (decision 54 wave 3, section C, 2026-10-04).

NPS's passport stamp locations (`/passportstamplocations`) lands once, in nps/challenges.py; NPS's
list is read whole, nationally, so this folder, NPS's other, writes no resource for the same list
(decision 34).

The note this replaces read, whole:

National Park Service: challenges, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

The Passport booklet is sold by a partner. The stamp locations are free API data. Skeptic correction
(Measured): a `/passportstamplocations` row has no coordinates of its own, only `label`, `parks[]`
and a `type` such as `visitorcenters`. To place a stamp, join it to `/visitorcenters` or …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/passportstamplocations` (section C, 2026-10-04): landed by nps/challenges.py as nps_passport_stamp_locations, national.",
        "(the coverage audit, 2026-10-01) API `/passportstamplocations`: 1,092 stamp locations. Park pages such as `nps.gov/neri/planyourvisit/new-river-gorge-100-mile-challenge.htm`.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/passportstamplocations",
        "https://nps.gov/neri/planyourvisit/new-river-gorge-100-mile-challenge.htm",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
