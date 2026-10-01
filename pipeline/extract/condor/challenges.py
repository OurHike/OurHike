"""Condor Trail Association: challenges, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('WP search for "challenge" returned 1 hit, the volunteer page.',),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://condortrail.com/",
    ),
)
