"""Alaska Trails: photos, nothing published (coverage audit 2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/photocontest` states no licence.",),
    where=(
        "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services",
        "https://alaska-trails.org/",
    ),
)
