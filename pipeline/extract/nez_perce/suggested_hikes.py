"""Nez Perce (Nee-Me-Poo) Trail Foundation: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Driving tours

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Auto Tour guides linked from `nezpercetrail.net/virtual-tour/` → "
        "`fs.usda.gov/detail/npnht/maps-pubs/?cid=fsbdev3_055663` (PDF, old URL, not opened). "
        "`fs.usda.gov/trails/nez-perce-nht/maps-guides` lists maps for sale (Discover Your Northwest, USGS "
        "store)",
    ),
    where=(
        "https://nezpercetrail.net/virtual-tour/",
        "https://fs.usda.gov/detail/npnht/maps-pubs/?cid=fsbdev3_055663",
        "https://fs.usda.gov/trails/nez-perce-nht/maps-guides",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
