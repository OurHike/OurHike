"""Washington RCO — State Trails Database: places, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Aggregated from the agencies, and six years old.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`WA_Public_Lands_Inventory_2019/0`: 32,593 polygons (`Land_Owner`, `NAME`), last edit 2020-06-04. "
        "`Recreation_Provider_Inventory/2` Recreation Areas: 5,221.",
    ),
    where=(
        "https://gis.dnr.wa.gov/site1/rest/services",
        "https://gis.dnr.wa.gov/site3/rest/services",
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
        "https://trails-wa-rco.hub.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
