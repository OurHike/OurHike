"""Star-Spangled Banner NHT (NPS): podcasts, nothing published (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/multimedia/audio` stsp 0",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/stsp/",
    ),
)
