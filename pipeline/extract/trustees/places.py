"""The Trustees of Reservations: places, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Machine-readable and current.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'ArcGIS `TTOR_2`, "Trustees Properties": '
        "`https://services1.arcgis.com/whFP7sXcUCogtdJz/arcgis/rest/services/Trustees_props/FeatureServer/0`. "
        "137 polygons with PROPERTY, PROP_TYPE, TOWN, MGMT_REGION; lastEdit 2026-02-06. MassGIS "
        "`AGOL/openspace` has 613 rows with `OWNER_ABRV` or `MANAGR_ABRV` = 'TTOR'.",
    ),
    where=("https://services1.arcgis.com/whFP7sXcUCogtdJz/arcgis/rest/services/Trustees_props/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
