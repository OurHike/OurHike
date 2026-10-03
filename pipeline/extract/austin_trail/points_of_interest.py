"""The Trail Foundation (Austin): points of interest, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

Drinking fountains and restrooms appear only on the PDF map.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/visit-the-trail/maps-parking/` via WordPress REST `/wp-json/wp/v2/pages?slug=maps-parking` (modified"
        " 2025-10-28): 25 parking locations, with coordinates in Google Maps links. They are grouped as lots, "
        "metered, on-street and weekend-only.",
    ),
    where=("https://thetrailfoundation.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
