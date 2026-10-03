"""Pacific Crest Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

No licence is stated on these.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Trips/FeatureServer/0`: 155 polylines with `Trip_Type`, `Label`, `Distance_Mi`, `Total_Gain_ft` and a"
        " `CMS_ID` link back to the pcta.org trip pages; last edit 2026-10-01 (today). `Trip_Waypoints`: 69. "
        "`Trip_Polygons` also exists.",
    ),
    where=(
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Trips/FeatureServer/0",
        "https://pcta.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
