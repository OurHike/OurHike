"""National Pony Express Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

The Re-Ride (June 16–26, 2027) is an event, not a challenge

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/passportstamplocations` poex 12",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nationalponyexpress.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
