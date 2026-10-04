"""USDA Forest Service: photos, published on Flickr, and not landed (decision 54 wave 3, section C,
2026-10-04).

NEEDS A KEY OURHIKE DOES NOT HOLD: a photo's licence is per photo, and Flickr states it only through
its API's `license` field (flickr.people.getPublicPhotos with `extras=license`), which needs a
Flickr API key, issued by Flickr at https://www.flickr.com/services/apps/create/. No FLICKR_API_KEY
is in the extract's environment (checked 2026-10-04), so no Flickr reader is written; an account's
licence is never a photo's (the round brief's item 2). With a key, the reader reads it from the
environment and answers UNKNOWN without it, as NPS_API_KEY does (extract/_json_apis.py). The no-key
public feed (photos_public.gne) returns the newest 20 uploads only (the coverage audit), and RIDB's
`/media` sits behind its own key (401, the audit). The coverage audit listed this cell three times
(batches b6 and its skeptic), one dataset.

The note this replaces read, whole:

USDA Forest Service: photos, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Bulk or geotag access needs a Flickr API key. Licence is per photo, and 25 is one page, not the
account, so read each photo's licence at fetch time. How many photos show trail features rather than
events is Unvalidated: the newest uploads sampled are oil-and-gas site photos.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        '(the coverage audit, 2026-10-01) `https://www.flickr.com/photos/usforestservice/` ("Forest Service, USDA | Flickr", nsid `140082569@N07`): `photoCount` 14,717. All 25 photos on the first page carry Flickr licence id 10. One photo page (`/photos/usforestservice/55196746856/`) links `creativecommons.org/publicdomain/mark/1.0`, so id 10 is the Public Domain Mark. The no-key public feed `https://www.flickr.com/services/feeds/photos_public.gne?id=140082569@N07&format=json` returns the latest 20 uploads, newest 2026-04-09. RIDB `/media` is still behind the 401 key wall (UNKNOWN). The EDW recreation layers have no photo field …',
    ),
    where=(
        "https://www.flickr.com/services/apps/create/",
        "https://www.flickr.com/photos/usforestservice/",
        "https://www.flickr.com/services/feeds/photos_public.gne?id=140082569@N07&format=json",
        "https://creativecommons.org/publicdomain/mark/1.0",
        "https://fs.usda.gov/",
        "https://apps.fs.usda.gov/arcx/rest/services",
    ),
    reason="needs a key OurHike does not hold: a Flickr API key, issued by Flickr, for each photo's own licence",
)
