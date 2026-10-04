"""AMC's A.T. committee: suggested hikes, drawn from amc/suggested_hikes.py's `amc_itineraries` (decision 54
wave 5, section K, 2026-10-04).

The itineraries page the coverage audit names is the Appalachian Mountain Club's own, outdoors.org/resources/
itineraries/, and lands once, in amc/ (decision 34). The conditions page's 'Today's best bet hike' is a
conditions item, not a list of hikes.

The note this replaces read, whole:

Appalachian Mountain Club (A.T. sections): suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

Itinerary count not taken.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://www.outdoors.org/resources/itineraries/` (page;
"expert-curated outdoor itineraries"). The conditions page adds a "Today's best bet hike".

Its `where`: https://www.outdoors.org/resources/itineraries/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "amc/suggested_hikes.py's amc_itineraries reads https://www.outdoors.org/resources/itineraries/, ten trips, 2026-10-04",
    ),
    where=("https://www.outdoors.org/resources/itineraries/",),
    reason="drawn from amc/'s resource, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
