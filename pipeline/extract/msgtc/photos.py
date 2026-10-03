"""Monadnock-Sunapee Greenway Trail Club: photos, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('"Pics From Hiking Friends" is one post with no licence.',),
    where=(
        "https://nhgeodata.unh.edu/nhgeodata/rest/services",
        "https://msgtc.org/",
    ),
)
