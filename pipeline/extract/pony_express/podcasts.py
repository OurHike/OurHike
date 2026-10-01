"""National Pony Express Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Own: none in 57 pages. `NPSAPI/multimedia/audio` poex 0",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nationalponyexpress.org/",
    ),
)
