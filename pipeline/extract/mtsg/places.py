"""Mountains to Sound Greenway Trust: places, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same REST endpoint: parks and open spaces 57, cultural and natural heritage sites 41, museums and "
        "education centers 31, visitor information centers 6. The NHA boundary is "
        "`https://services.arcgis.com/b2nA3bRpH9jJyZOr/arcgis/rest/services/MTS_Boundary/FeatureServer` (1 "
        "polygon layer, item modified 2023-12-16).",
    ),
    where=("https://services.arcgis.com/b2nA3bRpH9jJyZOr/arcgis/rest/services/MTS_Boundary/FeatureServer",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
