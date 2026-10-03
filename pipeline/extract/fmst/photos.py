"""Friends of the Mountains-to-Sea Trail: photos, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

The Flickr API needs a key. Geotags not checked.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Flickr `https://www.flickr.com/photos/66217818@N04/`: 1,538 photos. All 25 sampled on page 1 carry "
        '`"license":4`, which is CC BY 2.0.',
    ),
    where=("https://www.flickr.com/photos/66217818@N04/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
