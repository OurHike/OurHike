"""AZGeo Data Hub: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('The same feed\'s category is "Current Closures, Restrictions, and Reroutes" (org_channels). Items not read.',),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://azgeo-open-data-agic.hub.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
