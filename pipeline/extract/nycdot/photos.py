"""NYC DOT: photos, published on Flickr, and not landed (decision 54 wave 3, section C, 2026-10-04).

NEEDS A KEY OURHIKE DOES NOT HOLD: a photo's licence is per photo, and Flickr states it only through
its API's `license` field (flickr.people.getPublicPhotos with `extras=license`), which needs a
Flickr API key, issued by Flickr at https://www.flickr.com/services/apps/create/. No FLICKR_API_KEY
is in the extract's environment (checked 2026-10-04), so no Flickr reader is written; an account's
licence is never a photo's (the round brief's item 2). With a key, the reader reads it from the
environment and answers UNKNOWN without it, as NPS_API_KEY does (extract/_json_apis.py).

The note this replaces read, whole:

NYC Department of Transportation: photos, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Street and project photography, not trail features. NC-ND is probably incompatible with mirroring
(the same open question as OPRHP's non-commercial clause). It is listed so the next pass does not
re-find it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        '(the coverage audit, 2026-10-01) Flickr `https://www.flickr.com/photos/nycstreets/`: `realname` "New York City Department of Transportation", `photoCount` 30,005. Licence id 16 on all 25 photos rendered, which is CC BY-NC-ND 4.0 in Flickr\'s licence table.',
    ),
    where=(
        "https://www.flickr.com/services/apps/create/",
        "https://www.flickr.com/photos/nycstreets/",
    ),
    reason="needs a key OurHike does not hold: a Flickr API key, issued by Flickr, for each photo's own licence",
)
