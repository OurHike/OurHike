"""Continental Divide Trail Society: closures, could not be told (coverage audit 2026-10-01, batch
p06_persist).

The CDT's live closures belong to `cdtc` and `usfs/`. The USFS regional closure layers are already
recorded by audit b6.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same. Tried: 1–7.",),
    where=("https://cdtsociety.org/",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
