"""Forest Park Conservancy: elevation, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The paper Visitor's Guide has profiles. Nothing is online.",),
    where=(
        "https://www.portlandmaps.com/od/rest/services",
        "https://forestparkconservancy.org/",
    ),
)
