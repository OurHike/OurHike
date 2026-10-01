"""NY State Parks / NYS GIS Clearinghouse: photos, published, and not landed (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

These are park-level pictures, not feature photos. OPRHP's own photo channel licenses nothing
openly, which makes it less likely the `ImageLink` pictures are open either (Reasoned). Whether
OPRHP's data terms (attribution, non-commercial) reach images hosted on parks.ny.gov is
@unvalidated. That is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`ParkPoints/0` `ImageLink` is populated on 214 of 262 rows, pointing at parks.ny.gov hero images (e.g."
        " `…/2025-10/Robert%20Moses_DSC8497.jpg.webp`). `hasAttachments` is false on the facilities, trails, "
        "ParkPoints, park polygon and EST layers.",
        "Skeptic additions (Measured 2026-10-01): OPRHP's Flickr, `flickr.com/photos/nysparks` (nsid "
        "`97323186@N05`, linked from `content.parks.ny.gov`), holds 7,076 photos. Its first page shows "
        '`"license":0` (All Rights Reserved) on 25 of 25. Flickr\'s server-rendered search over that account, '
        "filtered to licences 1–6, 9 and 10 (every CC licence plus CC0 and …",
    ),
    where=(
        "https://parks.ny.gov",
        "https://flickr.com/photos/nysparks",
        "https://content.parks.ny.gov",
        "https://services.arcgis.com/1xFZPtKn1wKC6POA/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
