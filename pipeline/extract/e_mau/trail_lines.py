"""E Mau Na Ala Hele: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Own: none

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same ALKA layers as `ala-kahakai`",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://emaunaalahele.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
