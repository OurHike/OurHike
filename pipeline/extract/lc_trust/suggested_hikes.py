"""Lewis and Clark Trust: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/thingstodo` lecl 13. Own `journey_stop` (79) is expedition chronology, not hikes",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://lewisandclark.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
