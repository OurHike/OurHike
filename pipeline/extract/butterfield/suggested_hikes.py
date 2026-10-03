"""Butterfield Overland Trail Association: suggested hikes, nothing published (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Own pages checked. `NPSAPI/thingstodo` buov 0",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://butterfieldtrail.org/",
    ),
)
