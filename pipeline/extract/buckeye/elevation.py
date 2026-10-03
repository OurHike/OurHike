"""Buckeye Trail Association: elevation, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

USGS 3DEP covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("BTA publishes no profile. FarOut, a paid third party, has one.",),
    where=(
        "https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services",
        "https://buckeyetrail.org/",
    ),
)
