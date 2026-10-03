"""Washington RCO — State Trails Database: suggested hikes, nothing published (coverage audit
2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("RCO is a grant office. Hike guides in Washington are WTA's, a separate catalogue row.",),
    where=(
        "https://gis.dnr.wa.gov/site1/rest/services",
        "https://gis.dnr.wa.gov/site3/rest/services",
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
        "https://trails-wa-rco.hub.arcgis.com/",
    ),
)
