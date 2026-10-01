"""National Washington-Rochambeau Revolutionary Route Association: suggested hikes, published, and not
landed (coverage audit 2026-10-01, batch c11_nht).

App-only

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: STQRY app "Washington Rochambeau Trail" (App Store id6467008765), "themed itineraries … '
        'approximately 70-100 high-potential sites" (store listing via search)',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://w3r-us.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
