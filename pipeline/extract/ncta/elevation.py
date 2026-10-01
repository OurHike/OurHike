"""North Country Trail Association: elevation, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Too narrow to load; USGS covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`kek_mileage_elev/FeatureServer/0`: 394 points with `Z`, Kekekabic section only, "Temporary Mileage '
        'Index", last edit 2021-01-12. `trls_other` rows carry `Max_Slope`/`Avg_Slope`.',
    ),
    where=("https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/kek_mileage_elev/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
