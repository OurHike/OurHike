"""Colorado Mountain Club: places, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

The terms block it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The Routes & Places library also holds places (campgrounds, huts, trailheads) with a coordinate. "
        'Example: `/education-adventure/trips/routes-places/abyss-lake-trail` gives "Address: -105.710909, '
        '39.51101561". HTML, Plone `eea.facetednavigation`.',
    ),
    where=("https://cmc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
