"""Society for the Protection of NH Forests: places, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Reservation boundaries.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same service, layer 4 "public_access_props selection": 32 polygons (2020-05-11). The sitemap lists'
        ' 184 `/property/` pages. The web map "Forest Society Conserved Lands Map" '
        '(`5f334186a1f74f7c92d23bdb8a49dd3c`) has "Forest Society Reservations" and "Conservation Easements" '
        "layers with no public URL.",
    ),
    where=("https://forestsociety.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
