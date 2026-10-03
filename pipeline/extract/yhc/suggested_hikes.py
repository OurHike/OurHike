"""York Hiking Club: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

Events, not lasting descriptions.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/activities/hikes`: this month\'s dated outings (e.g. 2026-10-03 "hike #17 along the Mason-Dixon Trail")',),
    where=("https://yorkhikingclub.com/",),
)
