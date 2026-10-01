"""Mid State Trail Association (PA): places, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

PDF.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/images/pdfs/mstresupplylist_2022-01-27.pdf` ("Mail Drop & Food Stores Table for Long Distance Backpackers").',),
    where=("https://hike-mst.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
