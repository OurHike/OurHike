"""AZGeo Data Hub: places, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/6` AZT Passages Segments: 138 polygons. `Land_Ownership_within_10_miles_of_AZ_Trail` exists; not probed.",
        "Skeptic adds: `Gateway_Community_Points/FeatureServer/0`: 22 gateway communities (`NAME`, `COUNTY`, "
        "`Weblink`), last edit 2025-12-28, owner `AZTrail`.",
    ),
    where=("https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Gateway_Community_Points/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
