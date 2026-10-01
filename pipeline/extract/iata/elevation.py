"""Ice Age Trail Alliance: elevation, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

USGS 3DEP covers Wisconsin.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`IAT_Segments1` declares `hasZ: true`, but the Z values sampled on "Janesville to Milton" are all 0 '
        '(13 vertices). The only elevation-like item among the 169 is an image, "Elevation Profile Widget '
        'Round".',
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://iceagetrail.org/",
    ),
)
