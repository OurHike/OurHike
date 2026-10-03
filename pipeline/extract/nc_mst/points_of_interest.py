"""NC Mountains-to-Sea Trail (state-published layer): points of interest, published, and not landed
(coverage audit 2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Public_Access_Points/0`: 226 (Land and Water Fund access points with `Trail_Name`), last edit "
        "2025-02-25. `NC_State_Parks_Points/0`: 48 park units, last edit 2026-09-02. No campsite, shelter or "
        "water layer among DPR's 88 services.",
    ),
    where=("https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
