"""Iditarod Historic Trail Alliance: photos, nothing published (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Site footer reads "All Rights Reserved". No open collection. Visitor Guide photos are credited to BLM',),
    where=(
        "https://gis.blm.gov/arcgis/rest/services",
        "https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services",
        "https://iditarod100.org/",
    ),
)
