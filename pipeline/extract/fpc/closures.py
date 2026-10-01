"""Forest Park Conservancy: closures, published, and not landed (coverage audit 2026-10-01, batch
p07_persist).

Licence: page prose, so 21(a) does not reach it; portland.gov terms not read. Folder: PP&R (new).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.portland.gov/parks/nature/trail-closures-and-delays`, HTML, "updated on September 28, '
        '2026". Forest Park entries: the Ridge Trail parking area on NW Bridge Avenue "is closed indefinitely '
        'due to safety concerns… falling rock", and Wildwood mile 15.2, "The bridge is closed". The page also '
        "covers River View Natural Area (Trails 3 and 6 closed) and Whitaker Ponds. It has no feed: the only "
        "`<link rel=alternate>` tags are hreflang. portland.gov robots.txt allows `` with `Crawl-delay: 2`. "
        'PP&R\'s GIS `Park_Closures/FeatureServer/0` holds 40 "Closed Assets" points, e.g. "Alberta Park – …',
    ),
    where=(
        "https://www.portland.gov/parks/nature/trail-closures-and-delays",
        "https://portland.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
