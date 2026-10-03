"""Forest Park Conservancy: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through _shared/portland_parks/ `portland_parks_closed_assets`, each
extracted once in its steward's folder (decision 34). Its portion is assigned in dbt.

Portland Parks & Recreation's trail closures and delays page
(https://www.portland.gov/parks/nature/trail-closures-and-delays, 'This page was updated on
September 28, 2026', six sections, Forest Park's among them) is PP&R's, read once in
_shared/portland_parks/ as `portland_parks_trail_closures` beside its closed-assets layer (decision
34). portland.gov's robots.txt asks Crawl-delay 2.

Before decision 53 phase B, 2026-10-03, this note read:

Forest Park Conservancy: closures, published, and not landed (coverage audit 2026-10-01, batch
p07_persist).

Licence: page prose, so 21(a) does not reach it; portland.gov terms not read. Folder: PP&R (new).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/portland_parks/ `portland_parks_closed_assets` (decision 53 phase B, 2026-10-03): `portland_parks_closed_assets` reads `Park_Closures/FeatureServer/0`",
        '`https://www.portland.gov/parks/nature/trail-closures-and-delays`, HTML, "updated on September 28, 2026". Forest Park entries: the Ridge Trail parking area on NW Bridge Avenue "is closed indefinitely due to safety concerns… falling rock", and Wildwood mile 15.2, "The bridge is closed". The page also covers River View Natural Area (Trails 3 and 6 closed) and Whitaker Ponds. It has no feed: the only `<link rel=alternate>` tags are hreflang. portland.gov robots.txt allows `` with `Crawl-delay: 2`. PP&R\'s GIS `Park_Closures/FeatureServer/0` holds 40 "Closed Assets" points, e.g. "Alberta Park – …',
    ),
    where=(
        "https://services.arcgis.com/quVN97tn06YNGj9s/arcgis/rest/services/Park_Closures/FeatureServer/0",
        "https://www.portland.gov/parks/nature/trail-closures-and-delays",
        "https://portland.gov",
    ),
    reason="drawn from _shared/portland_parks/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; and from its trail closures page, `portland_parks_trail_closures`",
)
