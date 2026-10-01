"""Wisconsin DNR Open Data: places, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`LF_DNR_MGD_PROP_WTM_Ext/0`: 1,978 property polygons (`PROP_NAME`, `PUBLIC_ACCESS`). `REC_OPPS/14` DNR"
        " Managed Lands: 1,457.",
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://dnrmaps.wi.gov/arcgis_image/rest/services",
        "https://services5.arcgis.com/Ul9AyFFeFTjf08DW/arcgis/rest/services",
        "https://data-wi-dnr.opendata.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
