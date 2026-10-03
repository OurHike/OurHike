"""Connecticut Forest & Park Association: photos, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No open collection found on the homepage nav or in the public ArcGIS items. "
        "`2019_Trail_Crew_Photos_(DO_NOT_DELETE)` is internal.",
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services",
        "https://ctwoodlands.org/",
    ),
)
