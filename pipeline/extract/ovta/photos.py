"""Overmountain Victory Trail Association: photos, drawn from nps/photos.py's `nps_gallery_assets`
(decision 54 wave 3, section C, 2026-10-04).

NPS's gallery assets (`/multimedia/galleries/assets`), one row per photo with its own credit and
licence lands once, in nps/photos.py, read for the park codes nps_alerts' `park_codes` map lists,
which include `ovvi`, and dbt assigns this folder its portion by each row's own park list (decision
34). It needs NPS_API_KEY; without it the table is withdrawn, never read as empty
(extract/_json_apis.py, 'THE KEY').

The note this replaces read, whole:

Overmountain Victory Trail Association: photos, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/multimedia/galleries/assets` (section C, 2026-10-04): landed by nps/photos.py as nps_gallery_assets, for nps_alerts' park codes; this folder's park code: ovvi.",
        '(the coverage audit, 2026-10-01) `NPSAPI/multimedia/galleries` ovvi 11. Own `ovta.org/page-1463391` "Photos" has no licence',
    ),
    where=(
        "https://developer.nps.gov/api/v1/multimedia/galleries/assets",
        "https://ovta.org/page-1463391",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
