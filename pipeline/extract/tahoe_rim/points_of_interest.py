"""Tahoe Rim Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The water layer is 3.5 years old. `RELIABILITY` is a planning label, not a report, and must never
render as current flow.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Water_Sources/0`: 126 (69 `Reliable`, 57 `Seasonal`), last edit 2023-04-05. `Points_of_Interest/0`: "
        "228 (Vista 149, Lake 23, Peak 21…), last edit 2020-12-13. `Trailheads/0`: 22, with `Toilet`, `Water`, "
        "`Parking_Capacity`. `Campgrounds/0`: 6. `Mile_Markers/0`: 170. `Vistas/0`: 297 (Adopt-a-Vista).",
        "Skeptic adds: `Trailheads_New_info_Tahoe_Rim_Trail/FeatureServer/0`: 22 trailheads with `Toilet`, "
        "`Water`, `Number_of_Parking_Stalls`, `Biking_Allowed`, `Picnic_Tables`, last edit 2024-10-21. It is "
        "newer than `Trailheads/0` (item modified 2020-01-29), so this is the trailhead layer to load. Also …",
    ),
    where=(
        "https://services7.arcgis.com/NchnBpgTjegMVinZ/arcgis/rest/services/Trailheads_New_info_Tahoe_Rim_Trail/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
