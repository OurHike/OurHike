"""National Pony Express Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Own tables carry names, not coordinates (from the WY page text)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `/historic-pony-express-trail/stations/` lists "197" stations over "1966 Miles" (MO 3, KS 13, NE '
        "38, CO 2, WY 43, UT 27, NV 47, CA 24), with per-state HTML tables of names. The page embeds NPS's "
        "`placestogo` map. Upstream: NTIR POIs `poex` 190; `POEX_…_ReRide_Exchange_Stations_2026_Layer_View` 96",
    ),
    where=("https://nationalponyexpress.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
