"""Florida Trail Association: elevation, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Checked: all 33 public items owned by `FloridaTrailAssociation` (one is a "Contour JPEG" image). `FNST'
        " Master` has `hasZ: false`. The maps-and-databook page sells paper only.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services",
        "https://floridatrail.org/",
    ),
)
