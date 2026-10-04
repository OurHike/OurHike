"""USGS (The National Map's folder): photos, the agency's science image gallery, and not landed (decision 54
wave 5, section K, 2026-10-04).

usgs.gov/products/multimedia-gallery/images answers our agent HTTP 200 (the coverage audit tried a browser's
agent; this read used ours): the agency's science images, newest first ('August 25, 2026 — Episode 54 of lava
fountaining at Kīlauea summit begins', an organizational chart), paged without end. The photos type attaches a
photograph to a point of interest on a trail (pipeline/ELT.md: 'photos.py | photo manifest rows, never pixels |
points_of_interest'), and nothing in the gallery names one; a reader that ties the agency's images to trail
places is not built here.

The note this replaces read, whole:

USGS — The National Map: photos, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Public domain, but off-topic: science imagery, not trail features.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): usgs.gov multimedia (images and audio) pages. Skeptic:
`https://www.usgs.gov/products/multimedia-gallery/images` answers HTTP 200 to a browser user agent.

Its `where`: https://www.usgs.gov/products/multimedia-gallery/images https://usgs.gov

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.usgs.gov/products/multimedia-gallery/images (HTTP 200, 232,559 bytes, 2026-10-04T18:41:36Z): science images, Kīlauea's fountaining among the newest",
    ),
    where=("https://www.usgs.gov/products/multimedia-gallery/images",),
    reason="not this type's use: science images tied to no point of interest on a trail",
)
