"""US Fish & Wildlife Service: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

The item describes it as the National Trails Inventory, collected to the Federal Trail Data
Standards. That is the same schema family as NPS and USFS (`TRNAME`, `TRCLASS`, `NATTRDESIGNATION`,
`PUBLICDISPLAY`, `DATAACCESS`, `SEASONAL`). The item text says Cycle 3 ran 2019–2022 "and may
contain …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/FWS_HQ_Trails_Cycle_3_Public_View/FeatureServer/1`"
        ' ("FWS HQ Trail Segments"). ArcGIS item `a0120cfde3dd4082bbee9deb280f2cfa`, owner `an email address`. '
        "6,420 polylines, 3,624 mi (sum of `SECLENGTHMI`). maxRecordCount 2,000. Last edit 2026-10-01 00:37 "
        "UTC. A trail-level table `Trails_Info` (layer 2) holds 2,982 rows.",
    ),
    where=(
        "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/FWS_HQ_Trails_Cycle_3_Public_View/FeatureServer/1",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
