"""Trail of Tears Association: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

`TRTYPE` is not evidence of walkability (finding 2)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NPSAGOL/TRTE_NHT/0`: 2,006 lines (1,467 "Standard Terra Trail", 539 "Water Trail"), edited 2026-09-17. `nps_trails`: 0',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nationaltota.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
