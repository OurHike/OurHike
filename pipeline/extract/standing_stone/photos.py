"""Standing Stone Trail Club: photos, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"History of the 1000 Steps in Pictures" is in the nav. ~~I did not open it~~',
        "Skeptic, opened 2026-10-01 (`/history-of-the-sst-in-pictures`): the server-rendered text is the "
        'heading alone, "History of the 1000 Steps Trail in Pictures". The images come from a Wix gallery with '
        "no caption or licence text. Nothing on the site states an open licence.",
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
)
