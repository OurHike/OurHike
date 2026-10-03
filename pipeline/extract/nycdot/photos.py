"""NYC Department of Transportation: photos, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Street and project photography, not trail features. NC-ND is probably incompatible with mirroring
(the same open question as OPRHP's non-commercial clause). It is listed so the next pass does not
re-find it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Flickr `https://www.flickr.com/photos/nycstreets/`: `realname` "New York City Department of '
        'Transportation", `photoCount` 30,005. Licence id 16 on all 25 photos rendered, which is CC BY-NC-ND '
        "4.0 in Flickr's licence table.",
    ),
    where=("https://www.flickr.com/photos/nycstreets/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
