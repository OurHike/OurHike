"""Mid State Trail Association (PA): points of interest, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

XLS. Ten years old.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://hike-mst.org/images/pdfs/2016-07-01-ths-geocoded.xls` ("Selected Trailhead Parking '
        'Locations", 36,352 B, last-modified 2016-08-02).',
    ),
    where=("https://hike-mst.org/images/pdfs/2016-07-01-ths-geocoded.xls",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
