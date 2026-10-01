"""NYC Department of Transportation: challenges, nothing published (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("DOT catalogue and AGOL listing.",),
    where=("https://nyc.gov/dot/",),
)
