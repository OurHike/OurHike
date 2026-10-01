"""NYC Department of Transportation: suggested hikes, nothing published (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The DOT greenway pages describe systems, not routes. The NYC Bike Map (`nyc.gov/bikemap`) is a cycling"
        " map. `Summer_Street_2026_View` is an annual car-free event route.",
    ),
    where=("https://nyc.gov/bikemap",),
)
