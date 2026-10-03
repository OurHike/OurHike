"""Colorado Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

I did not count the hiking subset because the activity facet parameter did not take. The terms block
it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.cmc.org/education-adventure/trips/routes-places/@@faceted_query?b_start=0` reports 1,354 "
        "results across all activities, including climbing and camping. Each record gives land manager, "
        'distance and gain in its "alternate titles", parking permit, party size, trailhead coordinate, and '
        '"Recommended Maps: COTREX".',
    ),
    where=("https://www.cmc.org/education-adventure/trips/routes-places/@@faceted_query?b_start=0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
