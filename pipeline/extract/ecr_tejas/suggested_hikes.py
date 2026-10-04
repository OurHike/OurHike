"""El Camino Real de los Tejas NHT Association: suggested hikes, drawn from nps/suggested_hikes.py's
`nps_things_to_do and nps_tours` (decision 54 wave 3, section C, 2026-10-04).

NPS's things to do (`/thingstodo`) and tours (`/tours`) lands once, in nps/suggested_hikes.py, read
whole, nationally, so park code `elte` is in it, and dbt assigns this folder its portion by each
row's own park list matched to nps_alerts' `park_codes` map, the one home for which folder draws on
which park (decision 34). It needs NPS_API_KEY; without it the table is withdrawn, never read as
empty (extract/_json_apis.py, 'THE KEY').

The note this replaces read, whole:

El Camino Real de los Tejas NHT Association: suggested hikes, published, and not landed (coverage
audit 2026-10-01, batch c11_nht).

Private land, by reservation. Any listing must carry that

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/thingstodo` (section C, 2026-10-04): landed by nps/suggested_hikes.py as nps_things_to_do and nps_tours, national; this folder's park code: elte.",
        '(the coverage audit, 2026-10-01) Own: `/brazos-region/` "Walk the Ranchería Grande", "2.2 miles round trip on private property", reservation required, "watch out for holes, sticks, snakes". `NPSAPI/thingstodo` elte 10 ("Hike on El Camino Real de los Tejas")',
    ),
    where=(
        "https://developer.nps.gov/api/v1/thingstodo",
        "https://developer.nps.gov/api/v1/tours",
        "https://elcaminorealdelostejas.org/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
