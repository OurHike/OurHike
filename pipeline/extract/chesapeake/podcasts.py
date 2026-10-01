"""Chesapeake Conservancy: podcasts, nothing published (coverage audit 2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Own nav checked. `NPSAPI/multimedia/audio` cajo 0",),
    where=(
        "https://cicgis.org/arcgis/rest/services",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://chesapeakeconservancy.org/",
    ),
)
