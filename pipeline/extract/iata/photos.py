"""Ice Age Trail Alliance: photos, could not be told (coverage audit 2026-10-01, batch c10_nst_rest).

Not rounded down.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The homepage links Facebook, Instagram and TikTok only. `/iata/media-room/` was not read because "
        "robots.txt blocks it. The 7 ArcGIS `Image` items are site graphics.",
    ),
    where=("https://iceagetrail.org/",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
