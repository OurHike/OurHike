"""Mohonk Preserve: places, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

One row. It is the cheapest new place in this batch, and the licence footing is the same disclaimer
`mohonk_licence` ships on.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Mohonk_Preserve/FeatureServer/0`: 1 polygon, `dataLastEditDate` 2026-09-02, fields "
        "`Owner`/`Area`/`Perimeter`. `export_places.py` reads only `oprhp_park_polygons` (`PARKS_KEY`), so the "
        "preserve is not a searchable place today.",
    ),
    where=("https://services8.arcgis.com/cQ05sucxF4UWabFF/arcgis/rest/services/Mohonk_Preserve/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
