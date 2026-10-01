"""NYC Department of Transportation: elevation, nothing published (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked the 240 DOT catalogue entries and the 212 AGOL service names. The DEM is OTI's (see NYC Parks).",),
    where=("https://nyc.gov/dot/",),
)
