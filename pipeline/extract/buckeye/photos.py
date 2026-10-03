"""Buckeye Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Section photos are named `…-permission.jpg`, meaning used by permission, not openly licensed. The "
        'terms call all content "the exclusive property of the Organization or its content suppliers".',
    ),
    where=(
        "https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services",
        "https://buckeyetrail.org/",
    ),
)
