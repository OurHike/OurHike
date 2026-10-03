"""E Mau Na Ala Hele: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Event-shaped. A route has to be inferred

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/upcoming-events.html`, `/past-events.html` (HTML): e.g. the National Trails Day 2026 Kīholo Bay walk"
        ' with meeting directions; "walk & talk to Kauleolī and back"; a ~2-mile walk to Koʻa Heiau Holomoana',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://emaunaalahele.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
