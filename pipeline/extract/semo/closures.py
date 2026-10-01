"""Selma to Montgomery NHT (NPS): closures, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

The only live closures in this batch

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NPSAPI/alerts?parkCode=semo`: 2 "Park Closure": "Selma Interpretive Center Closed" (renovation, '
        '"completion is expected in 2028") and "Temporary Location - Selma Welcome Center Closed" (indexed '
        "2026-08-12/13)",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/semo/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
