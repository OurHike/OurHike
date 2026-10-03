"""Pinhoti Trail Alliance: photos, could not be told (coverage audit 2026-10-01, batch c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same.",),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://conservationgis.alabama.gov/adcnrweb/rest/services",
        "https://pinhotitrailalliance.org/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
