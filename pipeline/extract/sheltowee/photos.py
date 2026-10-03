"""Sheltowee Trace Association: photos, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("None from the STA. OutraGIS's map loads a 2019 Flickr photoset whose licences I did not read.",),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://sheltoweetrace.org/",
    ),
)
