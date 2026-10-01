"""National Pony Express Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The Re-Ride route is roads. Do not draw it as trail

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/POEX_NHT/0`: 1 line, 1:100k (2021-08-16). `nps_trails`: 0. The Re-Ride route "
        "`NPSAGOL/POEX_Pony_Express_ReRide_Route_2026_Layer_View`: 5,290 road segments (2026-09-23)",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nationalponyexpress.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
