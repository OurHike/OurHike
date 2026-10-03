"""Alaska Trails: elevation, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "36 services listed. `Mountain_Peaks/0` (658 peaks with `ELEV_FT`, a modified Esri layer) is a POI, not"
        " an elevation product.",
    ),
    where=("https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services",),
)
