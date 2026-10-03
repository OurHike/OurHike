"""NYC Department of Transportation: places, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Of marginal hiker value. Skeptic spot check 2026-10-01: `k5k6-6jex` still answers 93.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NYC DOT Pedestrian Plazas - Polygon` `k5k6-6jex`: 93 polygons, 2026-09-01, `plazaname`. "
        "`OSP_2026_Public_View` (Open Streets).",
    ),
    where=("https://data.cityofnewyork.us/d/k5k6-6jex",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
