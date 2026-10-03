"""National Washington-Rochambeau Revolutionary Route Association: podcasts, published, and not landed
(coverage audit 2026-10-01, batch c11_nht).

App-only

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Own: the same app, "seven hours of narrated stories and interviews" (store listing)',),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://w3r-us.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
