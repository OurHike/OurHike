"""Nez Perce Trail Foundation: suggested hikes, none published as a list (decision 54 wave 4, section K,
2026-10-04).

nezpercetrail.net/virtual-tour/ links the Forest Service's Auto Tour guides and links no PDF of its own; the Forest
Service's maps-and-guides page lists maps for sale. An auto tour is a drive, not a hike.

The note this replaces read, whole:

Nez Perce (Nee-Me-Poo) Trail Foundation: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Driving tours

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Auto Tour guides linked from `nezpercetrail.net/virtual-tour/` →
`fs.usda.gov/detail/npnht/maps-pubs/?cid=fsbdev3_055663` (PDF, old URL, not opened).
`fs.usda.gov/trails/nez-perce-nht/maps-guides` lists maps for sale (Discover Your Northwest, USGS store)

Its `where`: https://nezpercetrail.net/virtual-tour/
https://fs.usda.gov/detail/npnht/maps-pubs/?cid=fsbdev3_055663
https://fs.usda.gov/trails/nez-perce-nht/maps-guides

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://nezpercetrail.net/virtual-tour/ (HTTP 200, 22,176 bytes, 2026-10-04T17:38:59Z): no PDF linked, no distance stated",
    ),
    where=(
        "https://nezpercetrail.net/virtual-tour/",
        "https://fs.usda.gov/trails/nez-perce-nht/maps-guides",
    ),
    reason="not this type: auto tour guides (the Forest Service's) and maps for sale, no hike list",
)
