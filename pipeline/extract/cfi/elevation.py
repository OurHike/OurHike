"""Colorado Fourteeners Initiative: elevation, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The summit heights are POI attributes. There is no DEM and no profile.",),
    where=("https://14ers.org/",),
)
