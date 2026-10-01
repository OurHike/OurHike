"""Monadnock-Sunapee Greenway Trail Club: trail lines, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Restoring GRANIT would reverse #1711. On ArcGIS, only `scleclair` and `andyf0722`, both personal. NH
outside the WMNF currently has no club geometry for this trail.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Not loaded: the catalogue's `via: nh-granit` is retired (#1711). GRANIT still serves 19 `TRAILSYSTE` "
        'matches and 78 "Greenway"-named rows at '
        "`https://nhgeodata.unh.edu/nhgeodata/rest/services/CSD/RecreationResources/MapServer/2`. The club's "
        "own `/the-map/` is an image, and `MSGT-End2End-2021.pdf` is linked.",
    ),
    where=(
        "https://nhgeodata.unh.edu/nhgeodata/rest/services/CSD/RecreationResources/MapServer/2",
        "https://msgtc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
