"""NC Division of Parks & Recreation — NC Trails: places, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NC_State_Parks_System/FeatureServer/0` (ParkBoundaries): 346 polygons, edited 2026-09-30.",),
    where=("https://services6.arcgis.com/nRIB86xC7kq6wavB/arcgis/rest/services/NC_State_Parks_System/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
