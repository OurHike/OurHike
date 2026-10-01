"""Pacific Northwest Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Flickr `pntassociation`: 1,413 photos. The first 25 are all `license: 0` (All rights reserved).",),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services",
        "https://pnt.org/",
    ),
)
