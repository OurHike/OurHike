"""Friends of the Blue Hills: places, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

DCR's boundaries.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("MassGIS `AGOL/openspace/MapServer/0`: 94 rows with `SITE_NAME LIKE '%Blue Hills%'`. FBH `/directions/` page.",),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/openspace/MapServer/0",
        "https://friendsofthebluehills.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
