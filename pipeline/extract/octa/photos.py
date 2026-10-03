"""Oregon-California Trails Association: photos, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Own: UNKNOWN

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/multimedia/galleries` oreg 1, cali 2, each with `constraintsInfo`",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://octa-trails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
