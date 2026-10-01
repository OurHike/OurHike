"""North Country Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('WordPress search "photo": photography contests from 2009 and 2010 and youth exhibits. No licence anywhere.',),
    where=("https://northcountrytrail.org/",),
)
