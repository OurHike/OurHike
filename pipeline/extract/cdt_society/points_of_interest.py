"""Continental Divide Trail Society: points of interest, could not be told (coverage audit 2026-10-01,
batch p06_persist).

Do not round down. Nobody has read the Society's last good pages (Wayback captures 2021-12-14 and
2023-05-31, per audit c10's skeptic). A third party (pmags.com) says the Society is "no longer
active". That is Reasoned, not Measured. No licence to quote.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("No reachable source. Tried: 1, 2, 3, 4, 5, 6 and 7 as listed above.",),
    where=("https://pmags.com",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
