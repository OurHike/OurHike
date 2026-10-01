"""North Country Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same layer holds cautions, e.g. "Rough road – not mowed. Use caution while hiking." Also 18 `Ford`'
        " points in the POI layer, and `March_2025_Ice_Storm_Impacts/0` (1 polygon with an `alert` field, last "
        "edit 2025-08-08).",
    ),
    where=("https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
