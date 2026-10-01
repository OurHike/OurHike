"""AZGeo Data Hub: elevation, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

An attribute, not a product. USGS covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/1` points carry `Elevation` (3,041 rows).",),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://azgeo-open-data-agic.hub.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
