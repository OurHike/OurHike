"""Colorado Mountain Club: suggested hikes, inside its trip leaders' Routes & Places library, and not landed
(decision 54 wave 5, section K, 2026-10-04).

The Routes & Places library (@@faceted_query, '1354 results') is the club's catalogue for leading trips: climbs,
camps, ski tours, gym nights and 'Instructions for building a new Route & Place' sit beside hikes, each record's
distance and gain on its own page. Reading it is 68 listing pages and up to 1,354 records a month, and whether a
club's trip-leader library is a list of suggested hikes is the maintainer's call; neither is made here.

The note this replaces read, whole:

Colorado Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

I did not count the hiking subset because the activity facet parameter did not take. The terms block it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01):
`https://www.cmc.org/education-adventure/trips/routes-places/@@faceted_query?b_start=0` reports 1,354
results across all activities, including climbing and camping. Each record gives land manager, distance
and gain in its "alternate titles", parking permit, party size, trailhead coordinate, and "Recommended
Maps: COTREX".

Its `where`: https://www.cmc.org/education-adventure/trips/routes-places/@@faceted_query?b_start=0

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.cmc.org/education-adventure/trips/routes-places/@@faceted_query?b_start=0 (HTTP 200, 26,410 bytes, 2026-10-04T15:38:16Z): '1354 results', climbing, camping and hiking records",
    ),
    where=("https://www.cmc.org/education-adventure/trips/routes-places/",),
    reason="needs the maintainer's call: a trip leaders' library of every activity, 1,354 records",
)
