"""Potomac Heritage Trail Association: photos, drawn from nps/photos.py's `nps_gallery_assets`
(decision 54 wave 3, section C, 2026-10-04).

NPS's gallery assets (`/multimedia/galleries/assets`), one row per photo with its own credit and
licence lands once, in nps/photos.py, read for the park codes nps_alerts' `park_codes` map lists,
which include `pohe`, and dbt assigns this folder its portion by each row's own park list (decision
34). It needs NPS_API_KEY; without it the table is withdrawn, never read as empty
(extract/_json_apis.py, 'THE KEY').

The note this replaces read, whole:

Potomac Heritage Trail Association: photos, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/multimedia/galleries/assets` (section C, 2026-10-04): landed by nps/photos.py as nps_gallery_assets, for nps_alerts' park codes; this folder's park code: pohe.",
        "POHE_Scenic_View_Points/0 (116 points with photo_url, photo_cred, photo_use, photo_use_link and photo_use_notes, the coverage audit) is an unregistered ArcGIS layer, wave 1's format, named in section C's hand-back for the lead to route.",
        "(the coverage audit, 2026-10-01) NPS `/multimedia/galleries`: 18 for `pohe`. Licence is per asset (c9: filter `constraintsInfo` for public domain).",
        "(the coverage audit, 2026-10-01) Skeptic: `total` 18 confirmed. `POHE_Scenic_View_Points/0` (116) carries `photo_url`, `photo_cred`, `photo_use`, `photo_use_link` and `photo_use_notes`, a per-photo usage field that the first pass did not see. It was not profiled.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/multimedia/galleries/assets",
        "https://nps.gov/pohe/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
