"""Great Western Trail Association: photos, could not be told (coverage audit 2026-10-01, batch
c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same.",),
    where=(
        "https://apps.fs.usda.gov/fsgisx02/rest/services",
        "https://services2.arcgis.com/gdcQ6sUWKP8qwBmV/arcgis/rest/services",
        "https://americantrails.org/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
