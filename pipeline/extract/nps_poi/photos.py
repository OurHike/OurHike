"""National Park Service (points of interest): photos, drawn from nps/photos.py's `nps_gallery_assets`
(decision 54 wave 3, section C, 2026-10-04).

NPS's gallery assets (`/multimedia/galleries/assets`), one row per photo with its own credit and
licence lands once, in nps/photos.py; NPS's list is read for the park codes nps_alerts' map lists,
so this folder, NPS's other, writes no resource for the same list (decision 34).

The note this replaces read, whole:

National Park Service: photos, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Licence is per asset, so filter on `constraintsInfo.constraint == 'Public domain'`. NPGallery was
not opened.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/multimedia/galleries/assets` (section C, 2026-10-04): landed by nps/photos.py as nps_gallery_assets, for nps_alerts' park codes.",
        "nps/photos.py reads the gallery assets for the park codes the clubs draw on (nps_alerts' map), not NPS's whole list of about 206,685 assets (total read 2026-10-04): a national read is a monthly decision for the maintainer, as nps_alerts' national list is.",
        '(the coverage audit, 2026-10-01) API `/multimedia/galleries`: 10,507 galleries. Each has `constraintsInfo` (all 3 sampled read `Public domain`) and a copyright line: "Permission must be secured from the individual copyright owners…".',
    ),
    where=(
        "https://developer.nps.gov/api/v1/multimedia/galleries/assets",
        "https://nps.gov/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
