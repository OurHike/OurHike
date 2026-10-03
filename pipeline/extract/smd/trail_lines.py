"""Save Mount Diablo: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

A raster PDF behind an email gate and a terms ban. The worst format in the batch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/experience/trail-map/`: the Mount Diablo Regional Trail Map, Sixth Edition (GreenInfo Network "
        'cartography), as a digital PDF and a "georeferenced map that is compatible with … Avenza", both behind'
        " the email form. `/experience/trail-map/the-diablo-trail/` shows the 31-mi Diablo Trail as an image. "
        '`/curry-canyon-ranch-trails/` has an image map. The ArcGIS search "Save Mount Diablo" found 8 items, '
        "none owned by SMD.",
    ),
    where=("https://savemountdiablo.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
