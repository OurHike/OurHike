"""Star-Spangled Banner NHT (NPS): suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`NPSAPI/tours` "Baltimore Star-Spangled Tour" (4 stops, 3–8 h). `thingstodo` stsp 18',),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/stsp/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
