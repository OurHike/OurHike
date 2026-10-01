"""Ala Kahakai Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Land the org manages. It is the boundary data the `places` mart wants, but published as prose

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: land pages `/waikapuna`, `/kaunamano`, `/kawala`, `/manakaa`, `/kiolokaa-kaalualu`, `/kaiholena` "
        "(Squarespace HTML; acreage and history). `NPSAPI/places` alka ≥11",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://alakahakaitrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
