"""PASDA / PA DCNR: places, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`pasda/DCNR/MapServer/8` "State Parks 202503": 124 polygons. `/6` "BOF State Forests 202503": 670. '
        '`/9` "Wild and Natural Areas 202402": 141. `/18` "Local Park 202406": 6,325. `/15` Forest Districts.',
    ),
    where=("https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR/MapServer/8",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
