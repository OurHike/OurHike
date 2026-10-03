"""Oregon-California Trails Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Own: UNKNOWN

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NPSAPI/tours`: "Oregon Trail across Oregon & Washington" (20 stops, 1–7 days, a driving tour). '
        '`thingstodo`: "Hike on the Oregon Trail", "Hike on the California Trail"',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://octa-trails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
