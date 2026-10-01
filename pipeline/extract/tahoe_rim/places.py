"""Tahoe Rim Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Special_Management_Areas/0` (7 polygons: wilderness, state parks). `Desolation_Wilderness_Zones/0` "
        "(49). `trail_sections/0` (85).",
    ),
    where=(
        "https://services7.arcgis.com/NchnBpgTjegMVinZ/arcgis/rest/services",
        "https://tahoerimtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
