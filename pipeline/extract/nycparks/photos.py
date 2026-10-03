"""NYC Parks: photos, could not be told (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Whether Local Law 11 reaches images linked from a dataset is unsettled. Settling it takes OTI's
open-data team answering that question. Skeptic, 2026-10-01: UNKNOWN kept, with one more channel
closed. Flickr `https://www.flickr.com/photos/nycparks/` (`realname` "New York City Department of
Parks & …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The events feed's `image` field. `NYC Parks Events Listing – Event Images` `6eti-k994` (2023-10-02, "
        "stale). No licence statement covers the image bytes, which are hosted on nycgovparks.org.",
    ),
    where=(
        "https://www.flickr.com/photos/nycparks/",
        "https://data.cityofnewyork.us/d/6eti-k994",
        "https://nycgovparks.org",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
