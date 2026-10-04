"""NY State Parks: photos, on Flickr and on an unregistered ArcGIS layer, and not landed (decision 54
wave 3, section C, 2026-10-04).

NEEDS A KEY OURHIKE DOES NOT HOLD: a photo's licence is per photo, and Flickr states it only through
its API's `license` field (flickr.people.getPublicPhotos with `extras=license`), which needs a
Flickr API key, issued by Flickr at https://www.flickr.com/services/apps/create/. No FLICKR_API_KEY
is in the extract's environment (checked 2026-10-04), so no Flickr reader is written; an account's
licence is never a photo's (the round brief's item 2). With a key, the reader reads it from the
environment and answers UNKNOWN without it, as NPS_API_KEY does (extract/_json_apis.py).

ParkPoints/0's `ImageLink` (214 of 262 rows, the coverage audit) is an ArcGIS layer with no
sources.json row: wave 1's format, named in section C's hand-back for the lead to route; its images
state no licence.

The note this replaces read, whole:

NY State Parks / NYS GIS Clearinghouse: photos, published, and not landed (coverage audit
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
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) `ParkPoints/0` `ImageLink` is populated on 214 of 262 rows, pointing at parks.ny.gov hero images (e.g. `…/2025-10/Robert%20Moses_DSC8497.jpg.webp`). `hasAttachments` is false on the facilities, trails, ParkPoints, park polygon and EST layers.",
        "(the coverage audit, 2026-10-01) Skeptic additions (Measured 2026-10-01): OPRHP's Flickr, `flickr.com/photos/nysparks` (nsid `97323186@N05`, linked from `content.parks.ny.gov`), holds 7,076 photos. Its first page shows `\"license\":0` (All Rights Reserved) on 25 of 25. Flickr's server-rendered search over that account, filtered to licences 1–6, 9 and 10 (every CC licence plus CC0 and …",
    ),
    where=(
        "https://www.flickr.com/services/apps/create/",
        "https://parks.ny.gov",
        "https://flickr.com/photos/nysparks",
        "https://content.parks.ny.gov",
        "https://services.arcgis.com/1xFZPtKn1wKC6POA/arcgis/rest/services",
    ),
    reason="needs a key OurHike does not hold (Flickr's API, for each photo's own licence); the ArcGIS layer is wave 1's",
)
